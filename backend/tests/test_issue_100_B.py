"""Tests-first (phase A) — issue #100, chantier B (gazetteer unique des quartiers
de Metz). REFACTOR PUR : comportement strictement identique, sauf l'unique
harmonisation Q6 du libelle de secteur de Sainte-Therese (AC8).

Fichier de tests DEDIE (lecon 2026-06-12 fix-issue-80 : ne pas heurter un oracle
de harnais executant un fichier existant en sous-processus). Couvre AC1 a AC14 de
docs/specs/issue-100-B-SPEC.md §4. Suite GRATUITE, deterministe : aucun appel
reseau ni LLM (B est un refactor pur, spec §4 in fine). Isolation par les
fixtures autouse du conftest (init_db session-scope, reset caches) ; aucun cache
module-global introduit.

=============================================================================
PROTOCOLE GOLDEN ANTI-TAUTOLOGIE (spec §3.5, lecons faux-vert 2026-06-09 9.10 /
2026-06-13 / goldens-regeneres 2026-06-13) — A LIRE AVANT TOUTE MODIFICATION
=============================================================================
Les valeurs golden ci-dessous figent le comportement de l'ANCIEN code. Elles ont
ete capturees EN LITTERAL depuis l'etat ACTUEL des modules (avant toute derivation
depuis le gazetteer), via execution directe des modules
(ex. `python -c "from app.metz_local import _PROFILES; ..."`).
INTERDICTION ABSOLUE de regenerer un golden depuis le futur `geo_gazetteer` : un
golden ainsi produit passerait toujours et ne prouverait rien. Si la migration
change une valeur derivee, c'est la DERIVATION qui est fausse, pas le golden
(sauf l'unique exception Q6/Sainte-Therese, traitee par AC8 et exclue de AC4).

DEUX NATURES DE TESTS :
  - Groupe A (goldens de non-regression : AC1, AC3, AC4, AC5, AC7, AC9, AC11,
    AC13) : VERTS contre le code actuel ET apres migration. Garde-fous, pas des
    rouges-d'abord.
  - Groupe B (depend du gazetteer / changement voulu : AC2, AC6, AC8, AC14) :
    ROUGES maintenant (module `app.geo_gazetteer` absent, ou valeur Sainte-Therese
    pas encore harmonisee), VERTS apres que le developpeur a cree/branche le
    module. Les imports de `geo_gazetteer` sont LOCAUX a chaque test du groupe B
    pour que l'ImportError ne casse PAS la collecte du module (les goldens A
    restent collectables et verts).

PIEGE AC4 vs AC8 : aujourd'hui `_DISTRICT_TO_SECTOR["Sainte-Therese"]` vaut
"Sainte-Therese" (NON accentue, dette leguee par A). Apres B il devient
"Sainte-Thérèse" (ACCENTUE, harmonisation Q6 PRESERVANT l'affichage). AC4 (maps
secteur == golden ancien) EXCLUT donc l'entree du secteur de Sainte-Therese de sa
comparaison, sinon AC4 et AC8 se contrediraient. AC8 asserte la valeur DERIVEE
post-migration (jamais l'identite d'une cle de dict source, lecon 2026-06-16).
"""

from pathlib import Path

import pytest

import scrapers.base as base
import app.metz_local as metz_local
import app.market_stats as market_stats
from scrapers.base import canonical_district, canonical_city, extract_district


# Cle pivot et libelles de reference (spec §3.0 / §3.4).
CANON_ST = "Sainte-Therese"
LABEL_ST = "Sainte-Thérèse"           # libelle accentue (display + sector_display post-B)
COMPOSED_ST = "Sainte-Thérèse / Botanique"


# ===========================================================================
# GOLDENS LITTERAUX — captures depuis l'ETAT ACTUEL (avant migration).
# NE JAMAIS regenerer depuis geo_gazetteer (spec §3.5).
# ===========================================================================

# Golden 1 — scrapers.base._KNOWN_LOCALITIES (ordre exact actuel).
GOLDEN_KNOWN_LOCALITIES = [
    "le ban-saint-martin",
    "montigny-lès-metz",
    "montigny-les-metz",
    "longeville-lès-metz",
    "longeville-les-metz",
    "saint-julien-lès-metz",
    "saint-julien-les-metz",
    "scy-chazelles",
    "devant-les-ponts",
    "grange-aux-bois",
    "sainte-thérèse",
    "sainte-therese",
    "nouvelle ville",
    "plantières",
    "plantieres",
    "bellecroix",
    "vallières",
    "vallieres",
    "la patrotte",
    "outre-seille",
    "technopôle",
    "technopole",
    "queuleu",
    "sablon",
    "magny",
    "borny",
    "woippy",
    "plappeville",
    "lessy",
    "marly",
    "augny",
    "centre-ville",
    "centre",
]

# Formes derivees de QUARTIERS (sous-ensemble de _KNOWN_LOCALITIES geree par le
# gazetteer ; les communes de la couronne restent maintenues separement, spec
# §3.3.1). Sert au controle d'ordre long-avant-court (AC1).
GOLDEN_KNOWN_LOCALITIES_DISTRICTS = [
    "devant-les-ponts",
    "grange-aux-bois",
    "sainte-thérèse",
    "sainte-therese",
    "nouvelle ville",
    "plantières",
    "plantieres",
    "bellecroix",
    "vallières",
    "vallieres",
    "la patrotte",
    "outre-seille",
    "technopôle",
    "technopole",
    "queuleu",
    "sablon",
    "magny",
    "borny",
    "centre-ville",
    "centre",
]

# Golden 2/3 — metz_local._PROFILES (complet, champ par champ).
GOLDEN_PROFILES = {
    "Centre-Ville": {
        "name": "Centre-Ville",
        "center": "cœur du centre (cathédrale à quelques pas)",
        "gare": "~0,8 km (≈ 10 min à pied)",
        "caractere": "Hypercentre historique et commerçant, le plus recherché.",
    },
    "Ancienne-Ville": {
        "name": "Ancienne Ville",
        "center": "dans le centre historique",
        "gare": "~1 km",
        "caractere": "Vieille ville pavée autour de la colline Sainte-Croix.",
    },
    "Nouvelle-Ville": {
        "name": "Nouvelle Ville",
        "center": "~1 km du centre",
        "gare": "immédiate (~0,3 km)",
        "caractere": "Quartier Impérial autour de la gare, architecture germanique.",
    },
    "Les-Iles": {
        "name": "Les Îles",
        "center": "~1 km du centre",
        "gare": "~1,8 km",
        "caractere": "Quartier sur la Moselle (plan d'eau, lac Symphonie), prisé.",
    },
    "Outre-Seille": {
        "name": "Outre-Seille",
        "center": "accolé au centre (~0,8 km)",
        "gare": "~1,3 km",
        "caractere": "Quartier historique vivant, jouxte l'hypercentre à l'est.",
    },
    "Sablon": {
        "name": "Sablon",
        "center": "~1,8 km au sud",
        "gare": "~1,2 km",
        "caractere": "Quartier résidentiel familial au sud, proche gare.",
    },
    "Sainte-Therese": {
        "name": "Sainte-Thérèse",
        "center": "~2 km au sud",
        "gare": "~1,4 km",
        "caractere": "Petit quartier résidentiel sud, contigu au Sablon.",
    },
    "Queuleu": {
        "name": "Queuleu",
        "center": "~3 km au sud-est",
        "gare": "~2,5 km",
        "caractere": "Résidentiel pavillonnaire prisé et calme.",
    },
    "Plantieres": {
        "name": "Plantières",
        "center": "~2,5 km à l'est",
        "gare": "~2,5 km",
        "caractere": "Résidentiel, mixité de pavillons et d'immeubles.",
    },
    "Bellecroix": {
        "name": "Bellecroix",
        "center": "~2,5 km à l'est",
        "gare": "~2,8 km",
        "caractere": "Plateau à l'est (fort de Bellecroix), quelques vues dégagées.",
    },
    "Borny": {
        "name": "Borny",
        "center": "~4,5 km à l'est",
        "gare": "~4,5 km",
        "caractere": "Grand quartier est, secteur en rénovation urbaine.",
    },
    "Magny": {
        "name": "Magny",
        "center": "~5 km au sud",
        "gare": "~4,5 km",
        "caractere": "Secteur sud pavillonnaire, ambiance semi-résidentielle.",
    },
    "Vallieres": {
        "name": "Vallières",
        "center": "~4 km à l'est",
        "gare": "~4 km",
        "caractere": "Ancien village à l'est, dominante pavillonnaire.",
    },
    "Devant-Les-Ponts": {
        "name": "Devant-les-Ponts",
        "center": "~2 km au nord-ouest",
        "gare": "~2,5 km",
        "caractere": "Quartier nord-ouest résidentiel, proche de la Moselle.",
    },
    "La-Patrotte": {
        "name": "La Patrotte",
        "center": "~2,5 km au nord",
        "gare": "~3 km",
        "caractere": "Secteur nord populaire, en mutation.",
    },
    "Grange-Aux-Bois": {
        "name": "Grange-aux-Bois",
        "center": "~6 km à l'est",
        "gare": "~6 km",
        "caractere": "Quartier pavillonnaire récent à l'est, au calme.",
    },
    "Technopole": {
        "name": "Technopôle",
        "center": "~3,5 km au sud-est",
        "gare": "~3 km",
        "caractere": "Pôle tertiaire et universitaire, peu résidentiel.",
    },
}

# Golden 3 — metz_local._DIST_KM (complet).
GOLDEN_DIST_KM = {
    "Centre-Ville": {"center": 0.2, "gare": 0.8},
    "Ancienne-Ville": {"center": 0.4, "gare": 1.0},
    "Nouvelle-Ville": {"center": 1.0, "gare": 0.3},
    "Les-Iles": {"center": 1.0, "gare": 1.8},
    "Outre-Seille": {"center": 0.8, "gare": 1.3},
    "Sablon": {"center": 1.8, "gare": 1.2},
    "Sainte-Therese": {"center": 2.0, "gare": 1.4},
    "Queuleu": {"center": 3.0, "gare": 2.5},
    "Plantieres": {"center": 2.5, "gare": 2.5},
    "Bellecroix": {"center": 2.5, "gare": 2.8},
    "Borny": {"center": 4.5, "gare": 4.5},
    "Magny": {"center": 5.0, "gare": 4.5},
    "Vallieres": {"center": 4.0, "gare": 4.0},
    "Devant-Les-Ponts": {"center": 2.0, "gare": 2.5},
    "La-Patrotte": {"center": 2.5, "gare": 3.0},
    "Grange-Aux-Bois": {"center": 6.0, "gare": 6.0},
    "Technopole": {"center": 3.5, "gare": 3.0},
}

# Golden 3b — metz_local._ALIASES (complet, inclut le piege « / »).
GOLDEN_ALIASES = {
    "Centre": "Centre-Ville",
    "Plantieres-Queuleu": "Plantieres",
    "Queuleu-Plantieres": "Queuleu",
    "Iles": "Les-Iles",
    "Ile": "Les-Iles",
    "Sainte-Therese-/-Botanique": "Sainte-Therese",
}

# Golden 4 — market_stats._DISTRICT_TO_SECTOR (complet, ETAT ACTUEL).
# NB : "Sainte-Therese" -> "Sainte-Therese" est la dette A (non accentue). AC4
# l'EXCLUT de sa comparaison ; AC8 verrouille sa valeur post-migration accentuee.
GOLDEN_DISTRICT_TO_SECTOR = {
    "Ancienne-Ville": "Centre Ville",
    "Bellecroix": "Bellecroix - Vallières",
    "Borny": "Borny",
    "Centre-Ville": "Centre Ville",
    "Devant-Les-Ponts": "Devant-les-Ponts",
    "Grange-Aux-Bois": "Borny",
    "La-Patrotte": "Patrotte-Metz-Nord",
    "Les-Iles": "Centre Ville",
    "Magny": "Magny",
    "Nouvelle-Ville": "Centre Ville",
    "Outre-Seille": "Centre Ville",
    "Patrotte-Metz-Nord": "Patrotte-Metz-Nord",
    "Plantieres": "Plantières-Queuleu",
    "Plantieres-Queuleu": "Plantières-Queuleu",
    "Queuleu": "Plantières-Queuleu",
    "Sablon": "Sablon",
    "Sainte-Therese": "Sainte-Therese",
    "Technopole": "Borny",
    "Vallieres": "Bellecroix - Vallières",
    "Vallieres-Les-Bordes": "Bellecroix - Vallières",
}

# Golden 4 — market_stats._SECTOR_DISTRICTS (complet, ETAT ACTUEL).
# NB : la cle "Sainte-Therese" (non accentuee) deviendra "Sainte-Thérèse" apres
# B (AC8). AC4 EXCLUT cette entree de sa comparaison.
GOLDEN_SECTOR_DISTRICTS = {
    "Bellecroix - Vallières": ["Bellecroix", "Vallieres-Les-Bordes", "Vallieres"],
    "Borny": ["Borny", "Technopole", "Grange-Aux-Bois"],
    "Centre Ville": [
        "Centre-Ville",
        "Ancienne-Ville",
        "Nouvelle-Ville",
        "Les-Iles",
        "Outre-Seille",
    ],
    "Devant-les-Ponts": ["Devant-Les-Ponts"],
    "Magny": ["Magny"],
    "Patrotte-Metz-Nord": ["Patrotte-Metz-Nord", "La-Patrotte"],
    "Plantières-Queuleu": ["Plantieres-Queuleu", "Queuleu", "Plantieres"],
    "Sablon": ["Sablon"],
    "Sainte-Therese": ["Sainte-Therese"],
}

# Golden 4b — _scope_context (scope_name AFFICHE) par secteur, ETAT ACTUEL (AC7).
# Cle = sector_display attendu ; valeur = rendu _scope_context. La cle non
# accentuee "Sainte-Therese" est EXCLUE (elle change via Q6, AC8).
GOLDEN_SCOPE_CONTEXT_SECTEUR = {
    "Centre Ville": "Dans le secteur Centre Ville (quartiers voisins)",
    "Bellecroix - Vallières": "Dans le secteur Bellecroix - Vallières (quartiers voisins)",
    "Plantières-Queuleu": "Dans le secteur Plantières-Queuleu (quartiers voisins)",
    "Patrotte-Metz-Nord": "Dans le secteur Patrotte-Metz-Nord (quartiers voisins)",
    "Devant-les-Ponts": "Dans le secteur Devant-les-Ponts (quartiers voisins)",
    "Sablon": "Dans le secteur Sablon (quartiers voisins)",
    "Magny": "Dans le secteur Magny (quartiers voisins)",
    "Borny": "Dans le secteur Borny (quartiers voisins)",
}

# Golden 5 — canonical_district / canonical_city (ETAT ACTUEL, AC9). Fonctions
# d'ingestion : ne DOIVENT PAS changer (divergence stock prod <-> requete).
GOLDEN_CANONICAL_DISTRICT = {
    "Metz - Bellecroix": "Bellecroix",
    "Metz - Plantières - Queuleu": "Plantieres-Queuleu",
    "Metz": None,
    "Metz - Sablon": "Sablon",
    "Sainte-Thérèse": "Sainte-Therese",
    "Metz - Nouvelle Ville": "Nouvelle-Ville",
    "Metz - Les Îles": "Les-Iles",
    "Metz - Vallières-lès-Bordes": "Vallieres-Les-Bordes",
    "Metz - Sainte-Thérèse": "Sainte-Therese",
    "Bellecroix": "Bellecroix",
}
GOLDEN_CANONICAL_CITY = {
    "Sainte-Thérèse": "Sainte-Therese",
    "Nouvelle Ville": "Nouvelle-Ville",
    "Montigny-lès-Metz": "Montigny-Les-Metz",
    "METZ": "Metz",
    "le ban-saint-martin": "Le-Ban-Saint-Martin",
}

# Cle du secteur Sainte-Therese a EXCLURE des comparaisons golden AC4 (piege
# AC4/AC8). Valeur source actuelle (non accentuee) ; AC8 verrouille la valeur
# derivee post-migration (accentuee).
_ST_SECTOR_SOURCE = "Sainte-Therese"
_ST_SECTOR_TARGET = "Sainte-Thérèse"


def _import_gazetteer():
    """Import LOCAL du module gazetteer (cree par le DEVELOPPEUR, pas le testeur).

    Isole l'ImportError dans les seuls tests du groupe B : la collecte du module
    de test ne casse pas, les goldens A restent collectables et verts (spec §4 /
    consigne d'isolation). En phase A (module absent), les tests appelant cette
    fonction echouent proprement sur l'ImportError (rouge legitime), jamais sur
    une erreur de collecte parasite."""
    import app.geo_gazetteer as gz  # noqa: PLC0415 (import local volontaire)

    return gz


# ===========================================================================
# AC1 — _KNOWN_LOCALITIES derive == ancien, ordre long-avant-court (GOLDEN A)
# ===========================================================================

def test_ac1_known_localities_set_egal_golden():
    """AC1 (ensemble) — scrapers.base._KNOWN_LOCALITIES == golden 1 (ensemble).

    GOLDEN A : vert maintenant, doit le rester apres migration. Rouge si un
    libelle disparait/est ajoute ou si une commune est absorbee/perdue."""
    assert set(base._KNOWN_LOCALITIES) == set(GOLDEN_KNOWN_LOCALITIES), (
        "AC1 : l'ensemble _KNOWN_LOCALITIES doit egaler le golden fige avant "
        f"migration. Manquantes : {set(GOLDEN_KNOWN_LOCALITIES) - set(base._KNOWN_LOCALITIES)} ; "
        f"en trop : {set(base._KNOWN_LOCALITIES) - set(GOLDEN_KNOWN_LOCALITIES)}"
    )


def test_ac1_known_localities_ordre_long_avant_court():
    """AC1 (ordre) — pour toute paire de formes derivees de quartiers ou l'une
    est substring de l'autre, la plus LONGUE apparait avant la plus courte.

    GOLDEN A. extract_district renvoie le PREMIER match : un tri alphabetique
    naif ('centre' avant 'centre-ville') casserait le matching (spec §3.3.1,
    risque MOYEN). Falsifiabilite : rouge si l'ordre long-avant-court est casse.
    """
    forms = [f for f in base._KNOWN_LOCALITIES if f in set(GOLDEN_KNOWN_LOCALITIES_DISTRICTS)]
    pos = {f: i for i, f in enumerate(forms)}
    for a in forms:
        for b in forms:
            if a != b and a in b:
                # b est plus long et contient a -> b doit venir AVANT a.
                assert pos[b] < pos[a], (
                    f"AC1 : ordre long-avant-court casse : {b!r} (long) doit "
                    f"preceder {a!r} (court, substring) dans _KNOWN_LOCALITIES"
                )


# ===========================================================================
# AC2 — Couplage _PROFILES <-> _DIST_KM par construction (GROUPE B, ROUGE)
# ===========================================================================

def test_ac2_profiles_dist_km_memes_cles():
    """AC2 — set(_PROFILES.keys()) == set(_DIST_KM.keys()).

    Cette egalite est deja vraie aujourd'hui (verrouillee par AC9 de A) : ce
    sous-test reste vert. AC2 est complete par le test 'par construction'
    ci-dessous (groupe B, rouge tant que le gazetteer est absent)."""
    assert set(metz_local._PROFILES.keys()) == set(metz_local._DIST_KM.keys()), (
        "AC2 : _PROFILES et _DIST_KM doivent avoir EXACTEMENT les memes cles."
    )


def test_ac2_couplage_par_construction_via_gazetteer():
    """AC2 (par construction) — _PROFILES et _DIST_KM derivent du MEME jeu
    d'entrees du gazetteer : chaque entree porte profile ET dist_km (deux champs
    obligatoires de la meme entree), donc l'egalite des cles est structurelle.

    GROUPE B : ROUGE tant que app.geo_gazetteer n'existe pas (ImportError
    legitime). Preuve : l'ensemble des canonical_key du gazetteer == cles de
    _PROFILES == cles de _DIST_KM, et chaque entree a un dict profile non vide ET
    un dict dist_km avec center+gare."""
    gz = _import_gazetteer()
    gaz = gz.GAZETTEER
    keys_gaz = set(gaz.keys())
    assert keys_gaz == set(metz_local._PROFILES.keys()), (
        "AC2 : les cles du gazetteer doivent egaler celles de _PROFILES"
    )
    assert keys_gaz == set(metz_local._DIST_KM.keys()), (
        "AC2 : les cles du gazetteer doivent egaler celles de _DIST_KM"
    )
    for k, entry in gaz.items():
        profile = entry["profile"] if isinstance(entry, dict) else entry.profile
        dist_km = entry["dist_km"] if isinstance(entry, dict) else entry.dist_km
        assert profile, f"AC2 : entree {k!r} sans profile (champ obligatoire)"
        assert "center" in dist_km and "gare" in dist_km, (
            f"AC2 : entree {k!r} sans dist_km {{center, gare}} (champ obligatoire)"
        )


# ===========================================================================
# AC3 — _PROFILES / _DIST_KM derives == anciens (valeurs) (GOLDEN A)
# ===========================================================================

def test_ac3_profiles_egal_golden():
    """AC3 — metz_local._PROFILES == golden 2/3 (champ par champ, name inclus).

    GOLDEN A : vert maintenant, doit le rester. Rouge si un texte de profil
    change d'un seul quartier."""
    assert metz_local._PROFILES == GOLDEN_PROFILES, (
        "AC3 : _PROFILES doit egaler le golden fige avant migration "
        "(name/center/gare/caractere, quartier par quartier)"
    )


def test_ac3_dist_km_egal_golden():
    """AC3 — metz_local._DIST_KM == golden 3. GOLDEN A : rouge si une distance
    numerique change d'un seul quartier."""
    assert metz_local._DIST_KM == GOLDEN_DIST_KM, (
        "AC3 : _DIST_KM doit egaler le golden fige avant migration"
    )


# ===========================================================================
# AC4 — Maps secteur derivees == anciennes, SAUF l'entree Sainte-Therese (GOLDEN A)
# ===========================================================================

def test_ac4_district_to_sector_egal_golden_hors_sainte_therese():
    """AC4 — _DISTRICT_TO_SECTOR == golden 4, en EXCLUANT l'entree du quartier
    Sainte-Therese (piege AC4/AC8 : sa valeur change via Q6, verrouillee par AC8).

    GOLDEN A (sur le perimetre hors Sainte-Therese) : vert maintenant ET apres
    migration. La cle 'Sainte-Therese' est retiree des DEUX cotes pour ne pas
    contredire AC8 (qui asserte la valeur derivee accentuee post-migration)."""
    actual = dict(market_stats._DISTRICT_TO_SECTOR)
    expected = dict(GOLDEN_DISTRICT_TO_SECTOR)
    actual.pop(CANON_ST, None)
    expected.pop(CANON_ST, None)
    assert actual == expected, (
        "AC4 : _DISTRICT_TO_SECTOR (hors Sainte-Therese) doit egaler le golden. "
        f"Diff cles : {set(actual) ^ set(expected)}"
    )


def test_ac4_sector_districts_egal_golden_hors_sainte_therese():
    """AC4 — _SECTOR_DISTRICTS == golden 4, en EXCLUANT le secteur Sainte-Therese.

    GOLDEN A. La cle de secteur 'Sainte-Therese' (non accentuee) devient
    'Sainte-Thérèse' apres B (AC8) : on la retire des DEUX cotes. Les formes de
    stock ('Vallieres-Les-Bordes', 'Patrotte-Metz-Nord') doivent rester."""
    actual = dict(market_stats._SECTOR_DISTRICTS)
    expected = dict(GOLDEN_SECTOR_DISTRICTS)
    actual.pop(_ST_SECTOR_SOURCE, None)
    actual.pop(_ST_SECTOR_TARGET, None)
    expected.pop(_ST_SECTOR_SOURCE, None)
    expected.pop(_ST_SECTOR_TARGET, None)
    assert actual == expected, (
        "AC4 : _SECTOR_DISTRICTS (hors secteur Sainte-Therese) doit egaler le "
        f"golden. Diff cles : {set(actual) ^ set(expected)}"
    )


def test_ac4_formes_de_stock_preservees():
    """AC4 (renfort) — les formes de stock se canonicalisant vers une cle
    distincte ('Vallieres-Les-Bordes', 'Patrotte-Metz-Nord') restent dans les
    maps (golden), pour ne pas degrader le matching du stock prod.

    GOLDEN A : rouge si une forme de stock disparait de sa map."""
    assert market_stats._DISTRICT_TO_SECTOR.get("Vallieres-Les-Bordes") == "Bellecroix - Vallières"
    assert market_stats._DISTRICT_TO_SECTOR.get("Patrotte-Metz-Nord") == "Patrotte-Metz-Nord"
    assert "Vallieres-Les-Bordes" in market_stats._SECTOR_DISTRICTS["Bellecroix - Vallières"]


# ===========================================================================
# AC5 — _ALIASES derive == ancien (GOLDEN A)
# ===========================================================================

def test_ac5_aliases_egal_golden():
    """AC5 — metz_local._ALIASES == golden 3b, inclut le piege « / ».

    GOLDEN A : rouge si un alias disparait ou pointe vers une autre cle."""
    assert metz_local._ALIASES == GOLDEN_ALIASES, (
        "AC5 : _ALIASES doit egaler le golden fige avant migration"
    )
    assert metz_local._ALIASES.get("Sainte-Therese-/-Botanique") == "Sainte-Therese", (
        "AC5 : le piege « / » 'Sainte-Therese-/-Botanique' -> 'Sainte-Therese' "
        "doit etre preserve (AC4 de A non regresse)"
    )


# ===========================================================================
# AC6 — districts.ts == projection in_selector du gazetteer (GROUPE B, ROUGE)
# ===========================================================================

_FRONT = Path(__file__).resolve().parents[2] / "frontend" / "lib"


def _parse_metz_districts_ts():
    """Parse STATIQUE de METZ_DISTRICTS depuis frontend/lib/districts.ts : extrait
    les chaines de la liste, sans build front (spec §3.3.5 / AC6)."""
    import re

    src = (_FRONT / "districts.ts").read_text(encoding="utf-8")
    m = re.search(r"METZ_DISTRICTS\s*:\s*string\[\]\s*=\s*\[(.*?)\]", src, re.DOTALL)
    assert m, "AC6 : bloc METZ_DISTRICTS introuvable dans districts.ts"
    return set(re.findall(r'"([^"]+)"', m.group(1)))


def test_ac6_coherence_front_gazetteer_in_selector():
    """AC6 — ensemble des display_label des entrees in_selector == True du
    gazetteer == ensemble METZ_DISTRICTS parse depuis districts.ts.

    GROUPE B : ROUGE tant que app.geo_gazetteer n'existe pas (ImportError
    legitime). Falsifiabilite : rouge si un quartier in_selector est ajoute/retire
    du gazetteer sans MAJ de districts.ts (et inversement)."""
    gz = _import_gazetteer()
    selector = set(gz.selector_labels())
    front = _parse_metz_districts_ts()
    assert selector == front, (
        "AC6 : projection in_selector du gazetteer != METZ_DISTRICTS. "
        f"Dans gazetteer seul : {selector - front} ; "
        f"dans districts.ts seul : {front - selector}"
    )


# ===========================================================================
# AC7 — sector_display inchange pour les secteurs existants (GOLDEN A)
# ===========================================================================

@pytest.mark.parametrize("sector_display,expected_text", sorted(GOLDEN_SCOPE_CONTEXT_SECTEUR.items()))
def test_ac7_scope_context_secteur_inchange(sector_display, expected_text):
    """AC7 — _scope_context (scope_name affiche) inchange pour chaque secteur
    existant hors Sainte-Therese.

    GOLDEN A : vert maintenant ET apres migration (le sector_display derive doit
    rester strictement egal a l'ancien libelle). Rouge si un libelle de secteur
    change (ex. 'Centre-Ville' au lieu de 'Centre Ville')."""
    rendered = market_stats._scope_context(
        {"scope": "secteur", "scope_name": sector_display, "dpe_band": None}
    )
    assert rendered == expected_text, (
        f"AC7 : scope_name affiche pour {sector_display!r} attendu "
        f"{expected_text!r}, recu {rendered!r}"
    )


def test_ac7_secteurs_existants_presents_dans_maps():
    """AC7 (renfort) — chaque sector_display existant (hors Sainte-Therese) est
    bien une cle de _SECTOR_DISTRICTS et la valeur d'au moins un quartier dans
    _DISTRICT_TO_SECTOR. GOLDEN A."""
    for sector_display in GOLDEN_SCOPE_CONTEXT_SECTEUR:
        assert sector_display in market_stats._SECTOR_DISTRICTS, (
            f"AC7 : secteur {sector_display!r} absent de _SECTOR_DISTRICTS"
        )
        assert sector_display in set(market_stats._DISTRICT_TO_SECTOR.values()), (
            f"AC7 : secteur {sector_display!r} n'est la valeur d'aucun quartier"
        )


# ===========================================================================
# AC8 — Harmonisation Q6 Sainte-Therese : valeur DERIVEE accentuee (GROUPE B,
# ROUGE maintenant — seul AC « rouge d'abord » cote comportement)
# ===========================================================================

def test_ac8_district_to_sector_sainte_therese_accentue():
    """AC8 — _DISTRICT_TO_SECTOR['Sainte-Therese'] == 'Sainte-Thérèse' (accentue).

    ROUGE MAINTENANT (valeur source actuelle 'Sainte-Therese' non accentuee, dette
    A), VERT apres harmonisation Q6. Asserte la valeur DERIVEE (sortie de
    normalisation), JAMAIS l'identite d'une cle de dict source (lecon 2026-06-16).
    """
    assert market_stats._DISTRICT_TO_SECTOR.get(CANON_ST) == LABEL_ST, (
        "AC8 : apres harmonisation Q6, _DISTRICT_TO_SECTOR['Sainte-Therese'] doit "
        f"valoir {LABEL_ST!r} (accentue), recu "
        f"{market_stats._DISTRICT_TO_SECTOR.get(CANON_ST)!r}"
    )


def test_ac8_sector_districts_sainte_therese_mono_quartier():
    """AC8 — _SECTOR_DISTRICTS['Sainte-Thérèse'] == ['Sainte-Therese'] : secteur
    mono-quartier sous la cle accentuee.

    ROUGE MAINTENANT (la cle de secteur est encore 'Sainte-Therese' non accentue),
    VERT apres Q6. Rouge si un voisin est ajoute au secteur."""
    assert market_stats._SECTOR_DISTRICTS.get(LABEL_ST) == [CANON_ST], (
        f"AC8 : _SECTOR_DISTRICTS[{LABEL_ST!r}] doit valoir [{CANON_ST!r}], recu "
        f"{market_stats._SECTOR_DISTRICTS.get(LABEL_ST)!r}"
    )
    assert _ST_SECTOR_SOURCE not in market_stats._SECTOR_DISTRICTS, (
        "AC8 : la cle de secteur non accentuee 'Sainte-Therese' doit disparaitre "
        "au profit de la forme accentuee (harmonisation Q6, dette A resolue)"
    )


def test_ac8_gazetteer_sainte_therese_sector_fields():
    """AC8 — l'entree gazetteer Sainte-Therese porte sector_key == 'Sainte-Therese'
    et sector_display == 'Sainte-Thérèse'.

    GROUPE B : ROUGE tant que app.geo_gazetteer n'existe pas (ImportError
    legitime). Verrouille la source de l'harmonisation Q6."""
    gz = _import_gazetteer()
    entry = gz.GAZETTEER[CANON_ST]
    sector_key = entry["sector_key"] if isinstance(entry, dict) else entry.sector_key
    sector_display = entry["sector_display"] if isinstance(entry, dict) else entry.sector_display
    assert sector_key == CANON_ST, (
        f"AC8 : sector_key de Sainte-Therese attendu {CANON_ST!r}, recu {sector_key!r}"
    )
    assert sector_display == LABEL_ST, (
        f"AC8 : sector_display de Sainte-Therese attendu {LABEL_ST!r} (accentue), "
        f"recu {sector_display!r}"
    )


# ===========================================================================
# AC9 — canonical_district / canonical_city NON modifies (GOLDEN A)
# ===========================================================================

@pytest.mark.parametrize("raw,expected", sorted(GOLDEN_CANONICAL_DISTRICT.items(), key=lambda kv: kv[0]))
def test_ac9_canonical_district_inchange(raw, expected):
    """AC9 (1) — canonical_district(raw, 'Metz') == golden 5.

    GOLDEN A : caracterise que la fonction d'ingestion n'est PAS modifiee.
    Rouge si la sortie change (divergence stock prod <-> requete, ~17,7k
    comparables muets)."""
    assert canonical_district(raw, "Metz") == expected, (
        f"AC9 : canonical_district({raw!r}, 'Metz') attendu {expected!r}, "
        f"recu {canonical_district(raw, 'Metz')!r}"
    )


@pytest.mark.parametrize("raw,expected", sorted(GOLDEN_CANONICAL_CITY.items()))
def test_ac9_canonical_city_inchange(raw, expected):
    """AC9 (2) — canonical_city(raw) == golden 5 (accents/prefixe/separateurs).

    GOLDEN A : caracterise que canonical_city n'est PAS modifiee."""
    assert canonical_city(raw) == expected, (
        f"AC9 : canonical_city({raw!r}) attendu {expected!r}, "
        f"recu {canonical_city(raw)!r}"
    )


# ===========================================================================
# AC10 — Invariance Sainte-Therese bout en bout (chantier A) (GOLDEN A)
# ===========================================================================

def test_ac10_invariance_sainte_therese_bout_en_bout():
    """AC10 — les 4 chemins de A restent valides apres B.

    GOLDEN A : vert maintenant ET apres migration. NB : on n'asserte PAS ici la
    valeur (accentuee/non) du secteur de Sainte-Therese (elle change via Q6, cf.
    AC8) — seulement que la cle quartier 'Sainte-Therese' a bien un secteur."""
    # (1) extraction texte -> cle pivot
    extracted = extract_district("quartier Sainte-Thérèse à Metz")
    assert extracted is not None and canonical_city(extracted) == CANON_ST, (
        "AC10 : extract_district doit reconnaitre Sainte-Thérèse et converger "
        f"vers {CANON_ST!r} (recu {extracted!r})"
    )
    # (2) profil curate
    ctx = metz_local.local_context(LABEL_ST, "Metz")
    assert ctx is not None and ctx["district"] == LABEL_ST, (
        f"AC10 : local_context('{LABEL_ST}') doit retourner le profil "
        f"district=={LABEL_ST!r}"
    )
    # (3) alias « / » preserve
    ctx_composed = metz_local.local_context(COMPOSED_ST, "Metz")
    assert ctx_composed is not None and ctx_composed["district"] == LABEL_ST, (
        "AC10 : local_context du libelle compose « / » doit resoudre via l'alias"
    )
    # (4) presence d'un secteur pour la cle pivot (valeur non assertee ici, AC8)
    assert CANON_ST in market_stats._DISTRICT_TO_SECTOR, (
        "AC10 : _DISTRICT_TO_SECTOR doit contenir la cle 'Sainte-Therese'"
    )


# ===========================================================================
# AC11 — Invariance des autres quartiers (echantillon) (GOLDEN A)
# ===========================================================================

@pytest.mark.parametrize(
    "label,expected_key",
    [
        ("Nouvelle Ville", "Nouvelle-Ville"),
        ("Sablon", "Sablon"),
        ("Centre-Ville", "Centre-Ville"),
        ("Borny", "Borny"),
        ("Vallières", "Vallieres"),
    ],
)
def test_ac11_invariance_autres_quartiers(label, expected_key):
    """AC11 — local_context(q) retourne le meme dict (district + facts) et
    _resolve_key(q) la meme cle qu'avant B, pour un echantillon.

    GOLDEN A : on confronte au profil golden (capture avant migration) pour
    falsifiabilite (rouge si un profil derive differe de l'ancien)."""
    assert metz_local._resolve_key(label) == expected_key, (
        f"AC11 : _resolve_key({label!r}) attendu {expected_key!r}, "
        f"recu {metz_local._resolve_key(label)!r}"
    )
    ctx = metz_local.local_context(label, "Metz")
    assert ctx is not None, f"AC11 : profil {label!r} doit resoudre"
    golden = GOLDEN_PROFILES[expected_key]
    assert ctx["district"] == golden["name"], (
        f"AC11 : district attendu {golden['name']!r}, recu {ctx['district']!r}"
    )
    assert ctx["summary"] == golden["caractere"], (
        f"AC11 : summary (caractere) doit egaler le golden pour {label!r}"
    )
    # facts[0] = centre, facts[1] = gare : valeurs issues du profil golden.
    facts = ctx["facts"]
    assert facts[0]["value"] == golden["center"], (
        f"AC11 : fact 'centre' doit egaler le golden pour {label!r}"
    )
    assert facts[1]["value"] == golden["gare"], (
        f"AC11 : fact 'gare' doit egaler le golden pour {label!r}"
    )


# ===========================================================================
# AC12 — Suite A intacte sans modification (META)
# ===========================================================================

def test_ac12_suite_a_presente_et_non_dupliquee():
    """AC12 (meta) — test_issue_100_A.py est present et collectable, et ce fichier
    B ne le DUPLIQUE pas.

    L'orchestrateur relancera la suite A complete pour confirmer son vert ; ici on
    se borne a un invariant simple : presence du fichier A et de ses AC pivots,
    sans recopier ses tests. Falsifiabilite : rouge si le fichier A disparait."""
    a_path = Path(__file__).with_name("test_issue_100_A.py")
    assert a_path.exists(), "AC12 : test_issue_100_A.py doit exister (suite A intacte)"
    src = a_path.read_text(encoding="utf-8")
    # Invariant simple : la suite A garde son AC9 d'egalite des jeux de cles
    # (devient structurel en B mais le test A reste un consommateur valide).
    assert "test_ac9_egalite_jeux_de_cles_profiles_dist_km" in src, (
        "AC12 : la suite A doit conserver son test d'egalite _PROFILES/_DIST_KM"
    )
    # Ce fichier B ne redefinit aucun nom de test de A (pas de duplication).
    this_src = Path(__file__).read_text(encoding="utf-8")
    import re

    a_tests = set(re.findall(r"def (test_\w+)\(", src))
    b_tests = set(re.findall(r"def (test_\w+)\(", this_src))
    assert not (a_tests & b_tests), (
        f"AC12 : noms de tests dupliques entre A et B : {a_tests & b_tests}"
    )


# ===========================================================================
# AC13 — Trous de couverture documentes, PAS corriges (GOLDEN A)
# ===========================================================================

@pytest.mark.parametrize(
    "text",
    ["Ancienne Ville à Metz", "Les Îles à Metz"],
)
def test_ac13_trous_de_couverture_non_etendus(text):
    """AC13 — extract_district renvoie le MEME resultat qu'avant B (None : ces
    formes sont absentes de _KNOWN_LOCALITIES) ; la couverture n'est PAS etendue.

    GOLDEN A : rouge si B etend silencieusement la reconnaissance (ce ne serait
    plus un refactor pur)."""
    assert extract_district(text) is None, (
        f"AC13 : extract_district({text!r}) doit rester None (couverture NON "
        f"etendue par B), recu {extract_district(text)!r}"
    )


def test_ac13_commentaire_de_renvoi_lot_ulterieur():
    """AC13 — un commentaire documente que Ancienne-Ville / Les-Iles sont dans
    _PROFILES/_SECTORS_RAW/METZ_DISTRICTS mais pas dans les aliases_text
    (lot de correction ulterieur, hors B).

    GROUPE B (pres-requis prod) : la documentation sera dans geo_gazetteer.py ou
    base.py. Test statique tolerant : on cherche le renvoi dans base.py OU dans
    le gazetteer s'il existe. ROUGE tant que le commentaire n'est pas pose."""
    candidates = [Path(base.__file__).read_text(encoding="utf-8").lower()]
    gz_path = Path(base.__file__).resolve().parent / "geo_gazetteer.py"
    if not gz_path.exists():
        # chemin app/ depuis scrapers/base.py : remonte au package backend
        gz_path = Path(metz_local.__file__).resolve().parent / "geo_gazetteer.py"
    if gz_path.exists():
        candidates.append(gz_path.read_text(encoding="utf-8").lower())
    combined = "\n".join(candidates)
    has_ancienne = "ancienne" in combined and ("les-iles" in combined or "les iles" in combined or "îles" in combined)
    has_renvoi = "lot" in combined or "ulterieur" in combined or "ultérieur" in combined or "hors b" in combined or "couverture" in combined
    assert has_ancienne and has_renvoi, (
        "AC13 : un commentaire de renvoi (Ancienne-Ville / Les-Iles absents des "
        "aliases_text, correction lot ulterieur hors B) doit etre present dans "
        "base.py ou geo_gazetteer.py"
    )


# ===========================================================================
# AC14 — centroid vide, commune presente, schema (GROUPE B, ROUGE)
# ===========================================================================

def test_ac14_centroid_none_commune_metz():
    """AC14 — toute entree du gazetteer a centroid is None (geocodage = chantier
    C) et commune == 'Metz' ; le champ centroid existe dans le schema.

    GROUPE B : ROUGE tant que app.geo_gazetteer n'existe pas (ImportError
    legitime). Rouge si un centroide est rempli en B (sur-perimetre C) ou si
    commune est absent du schema."""
    gz = _import_gazetteer()
    for k, entry in gz.GAZETTEER.items():
        if isinstance(entry, dict):
            assert "centroid" in entry, f"AC14 : champ 'centroid' absent du schema pour {k!r}"
            centroid = entry["centroid"]
            commune = entry.get("commune")
        else:
            assert hasattr(entry, "centroid"), f"AC14 : champ 'centroid' absent du schema pour {k!r}"
            centroid = entry.centroid
            commune = entry.commune
        assert centroid is None, (
            f"AC14 : centroid doit etre None en B pour {k!r} (geocodage = chantier C), "
            f"recu {centroid!r}"
        )
        assert commune == "Metz", (
            f"AC14 : commune doit valoir 'Metz' pour {k!r}, recu {commune!r}"
        )
