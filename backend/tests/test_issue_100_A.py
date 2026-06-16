"""Tests-first (phase A) — issue #100, chantier A.

Fichier de tests DEDIE (lecon 2026-06-12 fix-issue-80 : ne pas heurter un oracle
de harnais qui executerait un fichier existant en sous-processus). Couvre les
criteres d'acceptation AC1 a AC15 de docs/specs/issue-100-A-SPEC.md §4.

Suite GRATUITE, deterministe : aucun appel reseau ni LLM reel. Les AC C2
(AC6/AC7/AC8) monkeypatchent `analyze_semantic` (vu depuis app.analysis), comme
le fait deja le harnais existant (test_photo_evidence_hardening, test_events,
test_issue_87_scope_warning). Isolation par les fixtures autouse du conftest
(init_db session-scope, reset caches) ; aucun cache module-global introduit.

Etat attendu en phase A : ROUGE pour la BONNE raison (fonctionnalite absente :
referentiel Sainte-Therese non ajoute, garde-fou C2 non implemente), jamais une
erreur de collecte parasite.
"""

from pathlib import Path

import pytest

from scrapers.base import (
    canonical_city,
    canonical_district,
    extract_district,
)
import scrapers.base as base
import app.metz_local as metz_local
import app.market_stats as market_stats


# Cle canonique pivot (SPEC §3.0) : les 4 referentiels DOIVENT y converger.
CANON = "Sainte-Therese"
# Libelle front / affiche (accent conserve, SANS « / », SPEC §2.4 / §3.4).
LABEL = "Sainte-Thérèse"
# Libelle compose piege par le separateur « / » (SPEC §3.0).
COMPOSED = "Sainte-Thérèse / Botanique"


# ===========================================================================
# Reconnaissance Sainte-Therese via les 4 chemins
# ===========================================================================

def test_ac1_extraction_texte_known_localities():
    """AC1 — extract_district reconnait Sainte-Therese dans un texte et la valeur
    extraite canonicalise vers la cle pivot."""
    extracted = extract_district("Bel appartement quartier Sainte-Thérèse à Metz")
    assert extracted is not None, (
        "AC1 : extract_district doit reconnaitre 'Sainte-Thérèse' "
        "(entree manquante dans _KNOWN_LOCALITIES ?)"
    )
    assert canonical_city(extracted) == CANON, (
        f"AC1 : la valeur extraite {extracted!r} doit canonicaliser vers {CANON!r}"
    )


def test_ac2_extraction_variante_sans_accent():
    """AC2 — variante sans accent 'sainte-therese' egalement reconnue."""
    extracted = extract_district("appartement sainte-therese metz")
    assert extracted is not None, (
        "AC2 : extract_district doit reconnaitre la variante sans accent "
        "'sainte-therese' (entree manquante dans _KNOWN_LOCALITIES ?)"
    )
    assert canonical_city(extracted) == CANON, (
        f"AC2 : {extracted!r} doit canonicaliser vers {CANON!r}"
    )


def test_ac3_profil_curate_local_context():
    """AC3 — local_context retourne le profil curate Sainte-Therese."""
    ctx = metz_local.local_context(LABEL, "Metz")
    assert ctx is not None, (
        "AC3 : local_context('Sainte-Thérèse','Metz') doit retourner un profil "
        "(entree _PROFILES['Sainte-Therese'] manquante ?)"
    )
    assert ctx["district"] == LABEL, (
        f"AC3 : district affiche attendu {LABEL!r}, recu {ctx.get('district')!r}"
    )
    assert ctx["summary"], "AC3 : summary doit etre non vide"
    assert ctx["facts"], "AC3 : facts doit etre non vide"
    assert ctx["precision"] == "quartier", (
        f"AC3 : precision attendue 'quartier', recue {ctx.get('precision')!r}"
    )


def test_ac4_alias_litteral_libelle_compose():
    """AC4 — l'alias litteral resout le libelle compose « / » piege.

    On passe SCIEMMENT le libelle compose (non canonique) : c'est tout l'enjeu du
    piege separateur (SPEC §3.0). Rouge si l'alias 'Sainte-Therese-/-Botanique'
    est absent de _ALIASES, OU si quelqu'un croit a tort que canonical_district
    gere le « / »."""
    # Sanity du piege : sans alias, la cle composee ne matche aucun profil.
    assert canonical_district(COMPOSED, "Metz") == "Sainte-Therese-/-Botanique", (
        "AC4 (sanity) : le piege « / » doit produire 'Sainte-Therese-/-Botanique' "
        "(si ce n'est plus le cas, canonical_district a ete modifie — hors perimetre)"
    )
    ctx = metz_local.local_context(COMPOSED, "Metz")
    assert ctx is not None, (
        "AC4 : local_context du libelle compose doit resoudre via l'alias litteral "
        "(alias 'Sainte-Therese-/-Botanique' manquant dans _ALIASES ?)"
    )
    assert ctx["district"] == LABEL, (
        f"AC4 : district affiche attendu {LABEL!r}, recu {ctx.get('district')!r}"
    )


def test_ac5_secteur_propre_market_stats():
    """AC5 — secteur propre dans market_stats : ne contient QUE Sainte-Therese."""
    assert CANON in market_stats._DISTRICT_TO_SECTOR, (
        "AC5 : _DISTRICT_TO_SECTOR doit contenir la cle 'Sainte-Therese' "
        "(secteur propre manquant dans _SECTORS_RAW ?)"
    )
    sector = market_stats._DISTRICT_TO_SECTOR[CANON]
    assert market_stats._SECTOR_DISTRICTS[sector] == [CANON], (
        f"AC5 : le secteur {sector!r} ne doit contenir QUE ['Sainte-Therese'], "
        f"recu {market_stats._SECTOR_DISTRICTS.get(sector)!r}"
    )


# ===========================================================================
# Garde-fou C2 (AC6 / AC7 / AC8) — LLM mocke (suite gratuite)
# ===========================================================================

def _semantic_result(district):
    """Resultat semantique deterministe (facade LLM). `district` = quartier que
    le LLM 'extrait' de l'annonce (= listing.district)."""
    return {
        "transparency_score": 80,
        "verdict": "Bonne",
        "risk_level": "Faible",
        "summary": "Annonce claire.",
        "risk_summary": "Peu de risques.",
        "questions": [],
        "negotiation_levers": [],
        # Une allegation de type 'centre' : pour Sainte-Therese (quartier sud,
        # ~proche centre/gare selon profil curate) un claim 'centre' a vocation a
        # etre juge 'coherent' SANS garde-fou ; AC6 verifie sa retrogradation.
        "local_claims": [{"text": "proche du centre", "type": "centre"}],
        "listing": {
            "city": "Metz",
            "district": district,
            "property_type": "appartement",
            "surface_m2": 70.0,
            "price_total": 210000.0,
            "dpe": None,
            "construction_year": None,
            "floor": None,
            "has_elevator": None,
            "has_terrace": None,
            "has_balcony": None,
            "has_cellar": None,
            "parking": None,
            "bedrooms": None,
            "condo_fees": None,
        },
    }


def _patch_semantic(monkeypatch, district):
    import app.analysis as analysis

    result = _semantic_result(district)
    monkeypatch.setattr(analysis, "analyze_semantic", lambda raw_text: result)
    return result


def test_ac6_override_non_corrobore_reserve_et_claims_retrogrades(monkeypatch):
    """AC6 — override NON corrobore : reserve presente + override conserve +
    aucun claim 'coherent'.

    L'annonce extrait 'Sainte-Thérèse' (listing.district) mais l'utilisateur a
    force 'Nouvelle Ville' : cles differentes -> non corrobore. Pas d'adresse ->
    branche sans geocodage (la seule ou C2 s'applique, SPEC §3.5.2)."""
    from app.analysis import run_full_analysis

    _patch_semantic(monkeypatch, district=LABEL)
    result = run_full_analysis(
        "Annonce de test, sans adresse.",
        district_override="Nouvelle Ville",
        address="",
    )
    lc = result["local_context"]
    assert lc is not None, "AC6 : local_context attendu non None (profil affiche)"
    assert "district_caveat" in lc, (
        "AC6 : la cle 'district_caveat' doit etre presente (override non corrobore)"
    )
    assert "non confirmé" in lc["district_caveat"], (
        "AC6 : la valeur de district_caveat doit contenir le substring stable "
        f"'non confirmé', recu {lc['district_caveat']!r}"
    )
    assert lc["district"] == "Nouvelle Ville", (
        "AC6 : l'override doit rester applique (Option 2, on ne supprime pas le "
        f"profil), recu {lc.get('district')!r}"
    )
    claims = lc.get("claims") or []
    assert claims, "AC6 : claims attendus non vides (sinon retrogradation non testee)"
    statuses = [c.get("status") for c in claims]
    assert "coherent" not in statuses, (
        f"AC6 : aucun claim ne doit rester 'coherent' (retrogradation a_verifier), "
        f"statuts recus : {statuses}"
    )


def test_ac7_override_corrobore_pas_de_reserve(monkeypatch):
    """AC7 — override corrobore (override et listing.district -> meme cle) :
    la cle 'district_caveat' est ABSENTE."""
    from app.analysis import run_full_analysis

    _patch_semantic(monkeypatch, district=LABEL)
    result = run_full_analysis(
        "Annonce de test, sans adresse.",
        district_override=LABEL,
        address="",
    )
    lc = result["local_context"]
    assert lc is not None, "AC7 : local_context attendu non None"
    assert "district_caveat" not in lc, (
        "AC7 : 'district_caveat' doit etre ABSENTE quand l'override est corrobore "
        "(reserve posee inconditionnellement ?)"
    )


def test_ac8_pas_override_pas_de_reserve(monkeypatch):
    """AC8 — pas d'override : pas de reserve (defaut neutre inchange).

    L'extraction fournit un quartier reconnu, mais sans override C2 ne s'applique
    jamais."""
    from app.analysis import run_full_analysis

    _patch_semantic(monkeypatch, district=LABEL)
    result = run_full_analysis(
        "Annonce de test, sans adresse.",
        district_override="",
        address="",
    )
    lc = result["local_context"]
    # local_context peut etre non None (profil reconnu) ; dans tous les cas, pas
    # de reserve sans override.
    if lc is not None:
        assert "district_caveat" not in lc, (
            "AC8 : 'district_caveat' ne doit JAMAIS apparaitre sans override"
        )


def test_ac8_default_behavior_local_context_unchanged():
    """AC8 (renfort) — l'appel par defaut de local_context (sans argument C2)
    ne porte JAMAIS district_caveat : le comportement actuel est strictement
    inchange."""
    ctx = metz_local.local_context(LABEL, "Metz")
    assert ctx is not None, "AC8 : profil Sainte-Therese attendu (prerequis AC3)"
    assert "district_caveat" not in ctx, (
        "AC8 : local_context appele par defaut ne doit pas poser district_caveat"
    )


# ===========================================================================
# Coherence inter-referentiels et non-regression
# ===========================================================================

def test_ac9_egalite_jeux_de_cles_profiles_dist_km():
    """AC9 — set(_PROFILES.keys()) == set(_DIST_KM.keys()).

    Verrouille le faux 'coherent' via le defaut {center:0,gare:0} si la cle manque
    dans _DIST_KM (metz_local assess_claims)."""
    assert set(metz_local._PROFILES.keys()) == set(metz_local._DIST_KM.keys()), (
        "AC9 : _PROFILES et _DIST_KM doivent avoir EXACTEMENT les memes cles. "
        f"Manquantes dans _DIST_KM : {set(metz_local._PROFILES) - set(metz_local._DIST_KM)} ; "
        f"manquantes dans _PROFILES : {set(metz_local._DIST_KM) - set(metz_local._PROFILES)}"
    )


def test_ac10_convergence_des_4_referentiels():
    """AC10 — les 4 referentiels convergent vers la cle pivot 'Sainte-Therese'.

    (1) label front, (2) extraction texte, (3) libelle secteur brut -> meme cle ;
    et cette cle est presente dans _PROFILES, _DIST_KM, _DISTRICT_TO_SECTOR."""
    # (1) label front -> cle (canonical_district avec ville, comme la requete reelle)
    assert canonical_district(LABEL, "Metz") == CANON, (
        f"AC10 : le label front {LABEL!r} doit resoudre vers {CANON!r}"
    )
    # (2) extraction texte -> cle
    extracted = extract_district(f"appartement {LABEL} a Metz")
    assert extracted is not None and canonical_city(extracted) == CANON, (
        "AC10 : l'extraction texte doit converger vers la cle pivot"
    )
    # (3) libelle brut du secteur _SECTORS_RAW -> cle (via canonical_district au
    # chargement, identique a _build_sector_maps).
    assert CANON in market_stats._SECTORS_RAW, (
        "AC10 : _SECTORS_RAW ne contient pas le libelle source de Sainte-Therese ?"
    )
    raw_labels = market_stats._SECTORS_RAW[CANON]
    assert [canonical_district(q, "Metz") for q in raw_labels] == [CANON], (
        f"AC10 : le secteur brut {raw_labels!r} doit canonicaliser vers [{CANON!r}]"
    )
    # Presence dans les 3 dicts backend.
    assert CANON in metz_local._PROFILES, "AC10 : absente de _PROFILES"
    assert CANON in metz_local._DIST_KM, "AC10 : absente de _DIST_KM"
    assert CANON in market_stats._DISTRICT_TO_SECTOR, (
        "AC10 : absente de _DISTRICT_TO_SECTOR"
    )


@pytest.mark.parametrize(
    "label,expected_name",
    [
        ("Nouvelle Ville", "Nouvelle Ville"),
        ("Sablon", "Sablon"),
        ("Centre-Ville", "Centre-Ville"),
    ],
)
def test_ac11_non_regression_profils_existants(label, expected_name):
    """AC11 — les profils preexistants restent inchanges apres l'ajout."""
    ctx = metz_local.local_context(label, "Metz")
    assert ctx is not None, f"AC11 : profil {label!r} doit toujours resoudre"
    assert ctx["district"] == expected_name, (
        f"AC11 : district attendu {expected_name!r}, recu {ctx.get('district')!r}"
    )


def test_ac12_non_regression_cascade_secteur():
    """AC12 — cascade secteur existante intacte : Nouvelle-Ville -> 'Centre Ville',
    taille du secteur 'Centre Ville' inchangee, Sainte-Therese PAS dedans."""
    assert market_stats._DISTRICT_TO_SECTOR.get("Nouvelle-Ville") == "Centre Ville", (
        "AC12 : _DISTRICT_TO_SECTOR['Nouvelle-Ville'] doit valoir 'Centre Ville' "
        f"(recu {market_stats._DISTRICT_TO_SECTOR.get('Nouvelle-Ville')!r})"
    )
    centre = market_stats._SECTOR_DISTRICTS.get("Centre Ville") or []
    # 5 quartiers d'origine (Centre-Ville, Ancienne-Ville, Nouvelle-Ville,
    # Les-Iles, Outre-Seille), Sainte-Therese exclue.
    assert len(centre) == 5, (
        f"AC12 : le secteur 'Centre Ville' doit garder 5 quartiers, recu {len(centre)} : {centre}"
    )
    assert CANON not in centre, (
        "AC12 : Sainte-Therese ne doit PAS etre rattachee a 'Centre Ville' (arbitrage 2.1)"
    )


# ===========================================================================
# Front (tests statiques sur les fichiers .ts)
# ===========================================================================

_FRONT = Path(__file__).resolve().parents[2] / "frontend" / "lib"


def test_ac13_selecteur_front_label_sans_slash():
    """AC13 — districts.ts contient 'Sainte-Thérèse' et AUCUNE entree avec « / »."""
    src = (_FRONT / "districts.ts").read_text(encoding="utf-8")
    assert f'"{LABEL}"' in src, (
        f"AC13 : METZ_DISTRICTS doit contenir l'entree exacte \"{LABEL}\""
    )
    # Aucune entree de quartier comportant « / » (eviter le piege separateur).
    offending = [ln for ln in src.splitlines() if "/" in ln and '"' in ln and "//" not in ln]
    assert not offending, (
        f"AC13 : aucune entree de district ne doit comporter « / », trouvees : {offending}"
    )


def test_ac14_type_local_context_porte_district_caveat():
    """AC14 — api.ts declare district_caveat? dans l'interface LocalContext."""
    src = (_FRONT / "api.ts").read_text(encoding="utf-8")
    assert "interface LocalContext" in src, "AC14 : interface LocalContext absente"
    # Localise le bloc de l'interface LocalContext pour ne pas matcher ailleurs.
    start = src.index("interface LocalContext")
    block = src[start:start + 600]
    assert "district_caveat?" in block, (
        "AC14 : le champ optionnel 'district_caveat?' doit etre declare dans "
        "l'interface LocalContext de api.ts"
    )


# ===========================================================================
# Limite documentee (anti sur-promesse)
# ===========================================================================

def test_ac15_botanique_absent_et_limite_documentee():
    """AC15 — 'botanique' absent de _KNOWN_LOCALITIES ; commentaire de renvoi au
    chantier C present dans le code (base.py ou metz_local.py)."""
    assert "botanique" not in [s.lower() for s in base._KNOWN_LOCALITIES], (
        "AC15 : 'botanique' ne doit PAS etre ajoute a _KNOWN_LOCALITIES "
        "(inter-communal Metz/Montigny -> chantier C, SPEC §2.2)"
    )
    base_src = Path(base.__file__).read_text(encoding="utf-8")
    metz_src = Path(metz_local.__file__).read_text(encoding="utf-8")
    combined = (base_src + metz_src).lower()
    assert "botanique" in combined and "chantier c" in combined, (
        "AC15 : un commentaire doit documenter que 'Botanique' (inter-communal) "
        "releve du chantier C (substring 'botanique' + 'chantier c' attendu)"
    )
