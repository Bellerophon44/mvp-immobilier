"""Probe read-only du gisement de re-list cross-source (chantier cross-agence,
increment 2b etape 1).

Estime un ORDRE DE GRANDEUR du re-list cross-source (un bien potentiellement
re-publie par une AUTRE source) par PROXY D'ATTRIBUTS, sans photo ni hash, pour
eclairer la decision d'engager l'etape 2. Ce n'est PAS du rattachement : la probe
n'ecrit RIEN (que des `db.query`), ne pose aucun `lineage_id`, ne touche pas
`market_stats`. Le resultat est une BORNE HAUTE (candidats potentiels), pas un
compte de vrais matches.

Lancement : `python -m tools.probe_cross_source` (rapport agrege sur stdout ;
`--out <fichier>` ecrit aussi un Markdown). Le rapport ne contient AUCUN id,
AUCUNE URL, AUCUNE donnee perso : que des compteurs agreges.
"""

from __future__ import annotations

import argparse
import logging
from datetime import datetime
from itertools import combinations
from typing import Optional

from db.session import SessionLocal, init_db
from db.models import Comparable

logger = logging.getLogger("probe_cross_source")

# Constantes du proxy (SPEC §3.3) — figees. Bornes INCLUSIVES.
_PROBE_GAP_DAYS_RECENT = 7     # "disparu" = non revu depuis > 7 jours
_PROBE_WINDOW_DAYS = 180       # B apparait dans les 180 j suivant la disparition de A
_PROBE_SURFACE_TOL = 0.10      # tolerance de surface du proxy (distinct du 2a +-2%)


def _source_couple(a: str, b: str) -> str:
    """Cle de couple non ordonne, triee lexicographiquement (`"a<->b"`) pour ne
    pas compter deux fois le meme couple de sources."""
    lo, hi = sorted((a, b))
    return f"{lo}<->{hi}"


def _is_disappeared(comp: Comparable, now: datetime) -> bool:
    return (
        comp.last_seen_at is not None
        and (now - comp.last_seen_at).days > _PROBE_GAP_DAYS_RECENT
    )


def _is_candidate_pair(a: Comparable, b: Comparable, now: datetime) -> bool:
    """Vrai si (A disparu, B apparu apres dans la fenetre) forme une paire
    candidate selon le proxy SPEC §3.3. A est suppose disparu (critere 2 deja
    verifie par l'appelant) ; B est le membre apparu apres."""
    if a.source == b.source:
        return False
    if b.first_seen_at is None or a.last_seen_at is None:
        return False
    if b.first_seen_at <= a.last_seen_at:
        return False
    if (b.first_seen_at - a.last_seen_at).days > _PROBE_WINDOW_DAYS:
        return False
    if a.property_type != b.property_type:
        return False
    if a.city != b.city:
        return False
    if a.postal_code is None or b.postal_code is None:
        return False
    if a.postal_code != b.postal_code:
        return False
    if not a.surface_m2 or not b.surface_m2:
        return False
    if abs(a.surface_m2 - b.surface_m2) > _PROBE_SURFACE_TOL * a.surface_m2:
        return False
    return True


def compute_probe(now: Optional[datetime] = None) -> dict:
    """Compteurs agreges du gisement candidat cross-source. LECTURE SEULE : que
    des `db.query`, aucun `db.add`/`commit`/`delete`. `now` injectable pour des
    bornes temporelles deterministes (defaut `datetime.utcnow()`).

    Retourne un dict de COMPTEURS AGREGES, sans aucun id/URL/donnee perso."""
    if now is None:
        now = datetime.utcnow()

    db = SessionLocal()
    try:
        comparables = db.query(Comparable).all()
    finally:
        db.close()

    total_comparables = len(comparables)
    by_source: dict[str, int] = {}
    for comp in comparables:
        by_source[comp.source] = by_source.get(comp.source, 0) + 1

    disappeared = [c for c in comparables if _is_disappeared(c, now)]

    total_pairs = 0
    pairs_by_source_couple: dict[str, int] = {}
    involved_ids: set[str] = set()

    # Une paire candidate associe un membre DISPARU (A) a un autre comparable (B)
    # apparu apres dans la fenetre. On considere les deux orientations (chaque
    # membre du couple peut etre le "disparu"), sans double-compter le couple.
    for x, y in combinations(comparables, 2):
        if _is_disappeared(x, now) and _is_candidate_pair(x, y, now):
            a, b = x, y
        elif _is_disappeared(y, now) and _is_candidate_pair(y, x, now):
            a, b = y, x
        else:
            continue
        total_pairs += 1
        couple = _source_couple(a.source, b.source)
        pairs_by_source_couple[couple] = pairs_by_source_couple.get(couple, 0) + 1
        involved_ids.add(a.id)
        involved_ids.add(b.id)

    involved_pct = (
        round(100.0 * len(involved_ids) / total_comparables, 1)
        if total_comparables
        else 0.0
    )

    return {
        "total_pairs": total_pairs,
        "pairs_by_source_couple": pairs_by_source_couple,
        "total_comparables": total_comparables,
        "disappeared": len(disappeared),
        "by_source": by_source,
        "involved_pct": involved_pct,
    }


def render_report(stats: dict) -> str:
    """Rapport texte/Markdown agrege a partir du dict `compute_probe`. AUCUN
    id/reference/URL/donnee perso : que des compteurs."""
    lines: list[str] = []
    lines.append("# Probe gisement re-list cross-source (read-only)")
    lines.append("")
    lines.append("## Compteurs agreges")
    lines.append(f"- Total comparables : {stats['total_comparables']}")
    lines.append(f"- Comparables disparus (> {_PROBE_GAP_DAYS_RECENT} j) : "
                 f"{stats['disappeared']}")
    lines.append(f"- Total paires candidates : {stats['total_pairs']}")
    lines.append(f"- Part du corpus impliquee : {stats['involved_pct']} %")
    lines.append("")
    lines.append("### Par source")
    for source in sorted(stats["by_source"]):
        lines.append(f"- {source} : {stats['by_source'][source]}")
    lines.append("")
    lines.append("### Par couple de sources")
    couples = stats["pairs_by_source_couple"]
    if couples:
        for couple in sorted(couples):
            lines.append(f"- {couple} : {couples[couple]}")
    else:
        lines.append("- (aucune paire candidate)")
    lines.append("")
    lines.append("## Limites")
    lines.append(
        "- Proxy d'attributs != vrai match : ces paires sont une BORNE HAUTE "
        "(candidats potentiels), pas un compte de re-lists reels. Le proxy ne "
        "distingue pas deux biens distincts de memes attributs d'un vrai re-list."
    )
    lines.append(
        "- Syndication bienici : bienici re-affiche des mandats de nos propres "
        "agences ; la syndication peut GONFLER (faux candidats syndiques) ou "
        "MASQUER (deja capte par 2a intra-reference) le vrai multi-mandat."
    )
    lines.append(
        "- Donnees jeunes : l'historique inc.1/2a est recent, peu de recul "
        f"temporel ; la fenetre de {_PROBE_WINDOW_DAYS} j est partiellement non "
        "observee."
    )
    lines.append(
        "- Conclusion : ce resultat est un INTRANT DE DECISION pour dimensionner "
        "l'etape 2, pas une verite sur le taux de re-list cross-source."
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=None,
                        help="Fichier Markdown de sortie (en plus de stdout).")
    args = parser.parse_args()

    init_db()
    stats = compute_probe()
    report = render_report(stats)
    print(report)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(report)
        logger.info("Rapport ecrit dans %s", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
