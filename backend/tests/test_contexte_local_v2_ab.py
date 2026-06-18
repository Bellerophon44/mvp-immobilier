"""Tests-first (phase A) — Contexte local v2, volets A et B (AC1-AC6).
Spec : docs/specs/contexte-local-v2-SPEC.md §3.A / §3.B / §5.

Volet A : retrait SEC du fact generique « Axe A31 · Luxembourg » en mode
QUARTIER (`metz_local.local_context`), 2 facts au lieu de 3 ; le mode ADRESSE
n'est PAS touche (le fact A31 y reste, porte une distance reelle).
Volet B : Pompidou devient un 4e fact DISTINCT en mode ADRESSE
(`metz_local.local_context_from_coords`), fusion `min(gare, pompidou)` supprimee.

ETAT ATTENDU EN PHASE A : ROUGE. Le code actuel produit 3 facts en mode quartier
(dont A31) et 3 facts fusionnes (gare+pompidou) en mode adresse. Ces tests
echouent donc legitimement tant que les volets A/B ne sont pas livres.

AUCUN appel reseau / LLM : on appelle directement les fonctions pures de
`metz_local` (mode quartier = district seul ; mode adresse = coords directes).
Isolation par les fixtures autouse du conftest.
"""

import re

import app.metz_local as metz_local
from app.metz_local import _A31_LUXEMBOURG, local_context, local_context_from_coords


# Coordonnees de test EXPLICITES (lat, lon) — un point dans Metz dont les
# distances Haversine aux POI gare et pompidou different nettement (AC5). On NE
# depend PAS d'un quartier reconnu : district=None est tolere (profil "Metz").
# Choisi a l'ouest de la gare pour que d(gare) << d(pompidou).
TEST_LAT = 49.1150
TEST_LON = 6.1650


# ===========================================================================
# Volet A — AC1 : 2 facts en mode quartier, sans A31/Luxembourg
# ===========================================================================
def test_ac1_quartier_two_facts_no_a31():
    """AC1 : en mode QUARTIER, exactement 2 facts dont les labels sont
    'Centre / Cathédrale St-Étienne' et 'Gare Metz-Ville · Centre Pompidou-Metz' ;
    aucun fact dont le label contient « A31 » ou « Luxembourg ».
    Rouge tant que A n'a pas retire le 3e fact (code actuel : 3 facts)."""
    ctx = local_context("Sablon")
    assert ctx is not None, "AC1 : Sablon est un quartier reconnu, ctx non-None attendu"
    facts = ctx["facts"]
    assert len(facts) == 2, (
        f"AC1 : exactement 2 facts en mode quartier attendus (A31 retire), recu "
        f"{len(facts)} : {[f['label'] for f in facts]}"
    )
    labels = [f["label"] for f in facts]
    assert labels == [
        "Centre / Cathédrale St-Étienne",
        "Gare Metz-Ville · Centre Pompidou-Metz",
    ], f"AC1 : labels attendus [centre, gare+pompidou], recu {labels}"
    for f in facts:
        assert "A31" not in f["label"] and "Luxembourg" not in f["label"], (
            f"AC1 : aucun label A31/Luxembourg en mode quartier, recu {f['label']!r}"
        )


# ===========================================================================
# Volet A — AC2 : suppression SECHE (pas reporte dans summary ni values)
# ===========================================================================
def test_ac2_quartier_no_a31_text_anywhere():
    """AC2 : en mode QUARTIER, ni une `value` de fact ni le `summary` ne contient
    la chaine `_A31_LUXEMBOURG`. La suppression est seche (pas un deplacement vers
    le summary). Rouge si le code verse _A31_LUXEMBOURG dans summary/value."""
    ctx = local_context("Sablon")
    assert ctx is not None
    assert _A31_LUXEMBOURG not in (ctx.get("summary") or ""), (
        "AC2 : _A31_LUXEMBOURG ne doit pas etre reporte dans le summary (suppression "
        "seche, pas un deplacement)"
    )
    for f in ctx["facts"]:
        assert _A31_LUXEMBOURG not in f.get("value", ""), (
            f"AC2 : _A31_LUXEMBOURG ne doit apparaitre dans aucune value, recu "
            f"{f.get('value')!r}"
        )
    # Doublement : la mention « Luxembourg » ne survit nulle part en mode quartier.
    blob = (ctx.get("summary") or "") + "".join(f.get("value", "") for f in ctx["facts"])
    assert "Luxembourg" not in blob, (
        "AC2 : aucune mention 'Luxembourg' ne doit subsister en mode quartier"
    )


# ===========================================================================
# Volet A — AC3 : le mode ADRESSE conserve le fact A31 (A ne le touche pas)
# ===========================================================================
def test_ac3_adresse_a31_fact_present_with_luxembourg():
    """AC3 : en mode ADRESSE, le fact 'Échangeur A31 le plus proche' est present
    et son `value` contient « Luxembourg » (A ne touche que le mode quartier).
    Rouge si A31 disparait du mode adresse."""
    ctx = local_context_from_coords(TEST_LAT, TEST_LON)
    facts = ctx["facts"]
    a31 = [f for f in facts if "A31" in f["label"]]
    assert a31, (
        f"AC3 : un fact 'Échangeur A31' attendu en mode adresse, recu labels "
        f"{[f['label'] for f in facts]}"
    )
    assert "Luxembourg" in a31[0]["value"], (
        f"AC3 : le value du fact A31 doit mentionner 'Luxembourg', recu "
        f"{a31[0]['value']!r}"
    )


# ===========================================================================
# Volet B — AC4 : 4 facts POI ordonnes en mode adresse
# ===========================================================================
def test_ac4_adresse_four_poi_facts_in_order():
    """AC4 : en mode ADRESSE, les 4 premiers facts (POI) ont les labels, DANS
    L'ORDRE : 'Centre / Cathédrale St-Étienne', 'Gare Metz-Ville',
    'Centre Pompidou-Metz', 'Échangeur A31 le plus proche'. Les facts ecoles
    (volet D) viennent APRES — on n'asserte donc que le prefixe des 4 POI.
    Rouge tant que B n'a pas demixe gare/pompidou (code actuel : 3 facts)."""
    ctx = local_context_from_coords(TEST_LAT, TEST_LON)
    facts = ctx["facts"]
    assert len(facts) >= 4, (
        f"AC4 : au moins 4 facts POI attendus en mode adresse, recu {len(facts)} : "
        f"{[f['label'] for f in facts]}"
    )
    poi_labels = [f["label"] for f in facts[:4]]
    assert poi_labels == [
        "Centre / Cathédrale St-Étienne",
        "Gare Metz-Ville",
        "Centre Pompidou-Metz",
        "Échangeur A31 le plus proche",
    ], f"AC4 : ordre/labels des 4 POI attendus, recu {poi_labels}"


# ===========================================================================
# Volet B — AC5 : values gare et Pompidou distincts (fusion supprimee)
# ===========================================================================
def test_ac5_gare_and_pompidou_values_distinct():
    """AC5 : quand les distances Haversine d['gare'] et d['pompidou'] different
    d'au moins 200 m, les `value` des facts gare et Pompidou sont DIFFERENTS
    (prouve que la fusion min(gare, pompidou) est supprimee). On choisit un point
    dont les deux distances different nettement (sonde explicite). Rouge tant que
    le code fusionne (les deux values seraient identiques)."""
    d = metz_local.precise_distances_km(TEST_LAT, TEST_LON)
    delta_m = abs(d["gare"] - d["pompidou"]) * 1000.0
    assert delta_m >= 200.0, (
        f"AC5 (pre-condition sonde) : les coords de test doivent ecarter gare et "
        f"pompidou d'>=200 m pour falsifier la fusion ; ecart={delta_m:.0f} m. "
        f"Ajuster TEST_LAT/TEST_LON si la geographie POI change."
    )

    ctx = local_context_from_coords(TEST_LAT, TEST_LON)
    by_label = {f["label"]: f for f in ctx["facts"]}
    assert "Gare Metz-Ville" in by_label and "Centre Pompidou-Metz" in by_label, (
        f"AC5 : facts gare ET pompidou distincts attendus, recu "
        f"{list(by_label)}"
    )
    gare_val = by_label["Gare Metz-Ville"]["value"]
    pompidou_val = by_label["Centre Pompidou-Metz"]["value"]
    assert gare_val != pompidou_val, (
        f"AC5 : value gare ({gare_val!r}) et pompidou ({pompidou_val!r}) doivent "
        f"differer (fusion min() supprimee)"
    )


# ===========================================================================
# Volet B — AC6 : aucun label ne fusionne 'Gare' et 'Pompidou' en mode adresse
# ===========================================================================
def test_ac6_adresse_no_label_merges_gare_and_pompidou():
    """AC6 : en mode ADRESSE, aucun label de fact ne contient a la fois « Gare » et
    « Pompidou » (fusion par label supprimee). Le mode quartier conserve son label
    fusionne (AC1) — distinction voulue. Rouge tant que le label adresse fusionne
    reste 'Gare Metz-Ville · Centre Pompidou-Metz'."""
    ctx = local_context_from_coords(TEST_LAT, TEST_LON)
    for f in ctx["facts"]:
        label = f["label"]
        merged = "Gare" in label and "Pompidou" in label
        assert not merged, (
            f"AC6 : aucun label ne doit fusionner Gare+Pompidou en mode adresse, "
            f"recu {label!r}"
        )

    # Garde-fou de contraste : en mode quartier la fusion par label RESTE (AC1) —
    # documente que la separation est specifique au mode adresse.
    q = local_context("Sablon")
    assert any(
        "Gare" in f["label"] and "Pompidou" in f["label"] for f in q["facts"]
    ), "AC6 (contraste) : le mode quartier conserve son label fusionne gare+pompidou"
