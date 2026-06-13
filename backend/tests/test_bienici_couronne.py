"""Tests-first (phase A) — chantier bienici-couronne.

SPEC : docs/specs/bienici-couronne-SPEC.md (§3 contrat technique, §4 les 7
critères d'acceptation). Objectif : faire collecter bien'ici sur TOUTES les
communes de `app.market_stats._METRO_CITIES` (Metz + couronne) au lieu de la
seule commune de Metz codée en dur (`BieniciScraper.city = "Metz"`).

Contrainte transverse (SPEC §4) : AUCUN appel réseau réel. On monkeypatche
`scrapers.sources.bienici.discover_zone_ids` (résolution de zone) et
`scrapers.sources.bienici.fetch_json` (annonces) avec des fakes déterministes.

Tant que le code de prod n'itère pas sur `_METRO_CITIES` (état actuel : une
seule commune "Metz"), AC1/AC2/AC3 (et AC5/AC7 selon le câblage) sont ROUGE
LÉGITIME (absence de feature, pas erreur de setup).

Note de conformité aux leçons (`.claude/lessons.md`) :
- AC1/AC2 captent les appels RÉELS à `discover_zone_ids` (mock instrumenté),
  pas un simple attribut de classe.
- AC5 asserte la PRÉSENCE réelle des comparables des communes valides (oracle
  de transit), pas seulement « ne lève pas » (leçon cross-agence-inc2b-etape1 :
  un AC « ne casse pas » est un faux-vert pour prouver un transit réel).
"""

import json

import pytest

import scrapers.sources.bienici as bienici
from scrapers.base import canonical_city
from scrapers.sources.bienici import (
    BieniciScraper,
    SURFACE_BUCKETS,
    MAX_PAGES,
    PAGE_SIZE,
    SOURCE_NAME,
    generate_stable_id,
)
from app.market_stats import _METRO_CITIES


# ---------------------------------------------------------------------------
# Helpers de mock (fakes déterministes, aucun réseau)
# ---------------------------------------------------------------------------

def _make_ad(ad_id, city):
    """Annonce bien'ici minimale mais VALIDE pour `_parse_listing` :
    adType buy, price/surfaceArea scalaires, propertyType résidentiel mappé,
    price/m2 dans la bande [800, 12000] (80 m² @ 250000 -> 3125 €/m²), ville
    exploitable. Toute valeur hors de ces contraintes serait rejetée en amont
    et masquerait l'oracle."""
    return {
        "id": ad_id,
        "adType": "buy",
        "propertyType": "flat",
        "price": 250000,
        "surfaceArea": 80,
        "city": city,
    }


def _zone_for(commune):
    """ZoneId interne factice et stable par commune (forme list comme l'API)."""
    return [f"zone-{commune}"]


def _commune_from_filters(params):
    """Retrouve la commune ciblée à partir des `params` passés à `fetch_json`.

    `_build_filters` sérialise les filtres dans `params["filters"]` (JSON) avec
    `zoneIdsByTypes.zoneIds`. On y relit le zoneId factice -> commune, ce qui
    permet au fake `fetch_json` de servir des annonces cohérentes par commune
    sans dépendre de l'ordre interne de la boucle de prod."""
    filters = json.loads(params["filters"])
    zone_ids = filters["zoneIdsByTypes"]["zoneIds"]
    assert zone_ids, "fetch_json appelé sans zoneIds (params: %r)" % (params,)
    # zoneId factice de la forme "zone-<commune>".
    first = zone_ids[0]
    assert isinstance(first, str) and first.startswith("zone-"), first
    return first[len("zone-"):]


def _install_discover_spy(monkeypatch, zone_map):
    """Installe un faux `discover_zone_ids` instrumenté.

    `zone_map` : dict commune -> liste de zoneIds (liste vide = résolution qui
    échoue, commune à sauter). Une commune absente de `zone_map` rend [].
    Retourne la liste (mutable) des communes effectivement demandées, dans
    l'ordre des appels, pour les oracles AC1/AC2."""
    calls = []

    def fake_discover(city_name):
        calls.append(city_name)
        return list(zone_map.get(city_name, []))

    monkeypatch.setattr(bienici, "discover_zone_ids", fake_discover)
    return calls


def _install_fetch_json(monkeypatch, ads_by_commune, counter=None):
    """Installe un faux `fetch_json` servant des annonces par commune.

    `ads_by_commune` : dict commune -> liste de dicts annonce. La première page
    sert toutes les annonces de la commune ; comme on en sert moins que
    PAGE_SIZE, la boucle de prod casse après la page 0 (pagination finie) ->
    1 appel par (commune résolue x bucket). `counter` (list) reçoit chaque
    params pour les oracles de bornage (AC6)."""

    def fake_fetch_json(url, params=None, **kwargs):
        if counter is not None:
            counter.append(params)
        commune = _commune_from_filters(params or {})
        ads = ads_by_commune.get(commune, [])
        # Une seule page : len(ads) < PAGE_SIZE -> la prod arrête le bucket.
        assert len(ads) < PAGE_SIZE, (
            "le fake sert moins de PAGE_SIZE annonces par page (oracle de "
            "pagination finie) ; reçu %d" % len(ads)
        )
        return {"realEstateAds": list(ads)}

    monkeypatch.setattr(bienici, "fetch_json", fake_fetch_json)


# ---------------------------------------------------------------------------
# AC1 — la liste des communes ciblées correspond exactement à _METRO_CITIES
# ---------------------------------------------------------------------------

def test_ac1_communes_ciblees_egalent_metro_cities(monkeypatch):
    """AC1 : l'ensemble des communes pour lesquelles le scraper tente une
    résolution de zone == set(_METRO_CITIES) (inclut "Metz"). Falsifiable :
    rouge si la liste reste ["Metz"] ou omet une commune de couronne."""
    # Toutes les communes résolvent (zone valide) pour isoler AC1 de AC5.
    zone_map = {c: _zone_for(c) for c in _METRO_CITIES}
    calls = _install_discover_spy(monkeypatch, zone_map)
    _install_fetch_json(monkeypatch, ads_by_commune={})

    BieniciScraper().scrape()

    assert set(calls) == set(_METRO_CITIES), (
        "communes résolues != _METRO_CITIES ; reçu %r (AC1)" % (sorted(set(calls)),)
    )
    assert "Metz" in calls, "Metz doit rester ciblée (AC1)"


# ---------------------------------------------------------------------------
# AC2 — discover_zone_ids appelé exactement une fois par commune
# ---------------------------------------------------------------------------

def test_ac2_discover_appele_une_fois_par_commune(monkeypatch):
    """AC2 : nb d'appels à discover_zone_ids == len(_METRO_CITIES) et chaque
    commune y figure une fois. Falsifiable : rouge si une seule commune est
    résolue, ou si une commune est appelée 0 ou plusieurs fois."""
    zone_map = {c: _zone_for(c) for c in _METRO_CITIES}
    calls = _install_discover_spy(monkeypatch, zone_map)
    _install_fetch_json(monkeypatch, ads_by_commune={})

    BieniciScraper().scrape()

    assert len(calls) == len(_METRO_CITIES), (
        "nb d'appels discover_zone_ids = %d, attendu %d (AC2)"
        % (len(calls), len(_METRO_CITIES))
    )
    # Exactement une fois chacune (pas de doublon, pas d'omission).
    for commune in _METRO_CITIES:
        assert calls.count(commune) == 1, (
            "%s appelé %d fois, attendu 1 (AC2)" % (commune, calls.count(commune))
        )


# ---------------------------------------------------------------------------
# AC3 — les comparables couvrent au moins deux communes distinctes de couronne
# ---------------------------------------------------------------------------

def test_ac3_comparables_couvrent_couronne_pas_que_metz(monkeypatch):
    """AC3 : avec un mock servant des annonces pour au moins deux communes
    distinctes de la couronne (Marly et Montigny-lès-Metz), le résultat de
    scrape() contient des PropertyListing dont la `city` couvre au moins deux
    communes distinctes de la couronne, sous forme canonique. Falsifiable :
    rouge si toutes les city sont "Metz" ou si la couronne est absente."""
    zone_map = {c: _zone_for(c) for c in _METRO_CITIES}
    calls = _install_discover_spy(monkeypatch, zone_map)

    ads_by_commune = {
        "Metz": [_make_ad("metz-1", "Metz")],
        "Marly": [_make_ad("marly-1", "Marly")],
        "Montigny-Les-Metz": [_make_ad("montigny-1", "Montigny-lès-Metz")],
    }
    _install_fetch_json(monkeypatch, ads_by_commune)

    results = BieniciScraper().scrape()

    cities = {r.city for r in results}
    couronne_marly = canonical_city("Marly")
    couronne_montigny = canonical_city("Montigny-lès-Metz")

    couronne_cities = cities - {canonical_city("Metz")}
    assert len(couronne_cities) >= 2, (
        "moins de 2 communes de couronne distinctes collectées : %r (AC3)" % (cities,)
    )
    assert couronne_marly in cities, "Marly absente du résultat (AC3)"
    assert couronne_montigny in cities, "Montigny-lès-Metz absente du résultat (AC3)"


# ---------------------------------------------------------------------------
# AC4 — la city stockée matche la forme de _METRO_CITIES (clé de cascade)
# ---------------------------------------------------------------------------

def test_ac4_city_canonicalisee_matche_metro_cities(monkeypatch):
    """AC4 : pour une annonce mockée ad.city == "MONTIGNY-LES-METZ"
    (casse/variante), le PropertyListing produit a
    city == canonical_city("Montigny-lès-Metz") et cette valeur appartient à
    _METRO_CITIES. Falsifiable : rouge si la city n'est pas canonicalisée
    (ne matcherait pas la cascade market_stats)."""
    zone_map = {c: _zone_for(c) for c in _METRO_CITIES}
    _install_discover_spy(monkeypatch, zone_map)

    ads_by_commune = {
        "Montigny-Les-Metz": [_make_ad("montigny-variante", "MONTIGNY-LES-METZ")],
    }
    _install_fetch_json(monkeypatch, ads_by_commune)

    results = BieniciScraper().scrape()

    expected = canonical_city("Montigny-lès-Metz")
    montigny = [r for r in results if r.city == expected]
    assert montigny, (
        "aucun PropertyListing avec city == %r ; cities reçues : %r (AC4)"
        % (expected, sorted({r.city for r in results}))
    )
    assert expected in _METRO_CITIES, (
        "%r n'appartient pas à _METRO_CITIES (clé de cascade) (AC4)" % (expected,)
    )


# ---------------------------------------------------------------------------
# AC5 — une commune sans zoneId est sautée sans interrompre les autres
# ---------------------------------------------------------------------------

def test_ac5_commune_sans_zone_sautee_sans_perdre_les_autres(monkeypatch):
    """AC5 : avec discover_zone_ids -> [] pour "Augny" mais des zoneIds valides
    pour les autres, scrape() NE LÈVE PAS, ET renvoie bien les comparables des
    communes valides (assertion de PRÉSENCE réelle, pas seulement « ne lève
    pas » — leçon lessons.md). Falsifiable : rouge si une exception remonte, ou
    si le résultat est vide / tronqué à la première commune en échec."""
    zone_map = {c: _zone_for(c) for c in _METRO_CITIES}
    zone_map["Augny"] = []  # résolution qui échoue -> commune sautée
    _install_discover_spy(monkeypatch, zone_map)

    ads_by_commune = {
        "Metz": [_make_ad("metz-ok", "Metz")],
        "Marly": [_make_ad("marly-ok", "Marly")],
        "Montigny-Les-Metz": [_make_ad("montigny-ok", "Montigny-lès-Metz")],
        # Augny ne sert rien (et de toute façon n'est jamais interrogée).
    }
    _install_fetch_json(monkeypatch, ads_by_commune)

    # Ne doit pas lever.
    results = BieniciScraper().scrape()

    cities = {r.city for r in results}
    # PRÉSENCE réelle des communes valides (oracle de transit) :
    assert canonical_city("Metz") in cities, "Metz absente après skip d'Augny (AC5)"
    assert canonical_city("Marly") in cities, "Marly absente après skip d'Augny (AC5)"
    assert canonical_city("Montigny-lès-Metz") in cities, (
        "Montigny absente après skip d'Augny (AC5)"
    )
    # Augny n'apparaît pas (pas de comparable fabriqué pour une commune sautée).
    assert canonical_city("Augny") not in cities, (
        "Augny ne devait produire aucun comparable (zone vide) (AC5)"
    )


# ---------------------------------------------------------------------------
# AC6 — le nombre de requêtes ADS est borné par communes x buckets x pages
# ---------------------------------------------------------------------------

def test_ac6_appels_ads_bornes(monkeypatch):
    """AC6 : avec un fetch_json comptant ses appels et des pages finies, le
    nombre total d'appels ADS est <= communes_résolues x len(SURFACE_BUCKETS)
    x MAX_PAGES. Falsifiable : rouge en cas de boucle non bornée / re-fetch
    incontrôlé."""
    zone_map = {c: _zone_for(c) for c in _METRO_CITIES}
    zone_map["Augny"] = []  # une commune non résolue n'engendre aucun appel ADS
    _install_discover_spy(monkeypatch, zone_map)

    resolues = [c for c in _METRO_CITIES if zone_map.get(c)]
    # Chaque commune résolue sert une annonce par page (moins de PAGE_SIZE ->
    # pagination finie : 1 page par bucket).
    ads_by_commune = {c: [_make_ad(f"{c}-1", c)] for c in resolues}
    counter = []
    _install_fetch_json(monkeypatch, ads_by_commune, counter=counter)

    BieniciScraper().scrape()

    plafond = len(resolues) * len(SURFACE_BUCKETS) * MAX_PAGES
    assert len(counter) <= plafond, (
        "appels ADS = %d > plafond %d (communes_résolues=%d x buckets=%d x "
        "pages=%d) (AC6)"
        % (len(counter), plafond, len(resolues), len(SURFACE_BUCKETS), MAX_PAGES)
    )
    # Borne basse de sanité : aucun appel ADS pour la commune non résolue.
    assert len(counter) <= len(resolues) * len(SURFACE_BUCKETS), (
        "pagination non finie : %d appels pour %d communes x %d buckets (AC6)"
        % (len(counter), len(resolues), len(SURFACE_BUCKETS))
    )


# ---------------------------------------------------------------------------
# AC7 — dédup intra-run inter-communes (seen partagé)
# ---------------------------------------------------------------------------

def test_ac7_dedup_inter_communes_seen_partage(monkeypatch):
    """AC7 : si deux communes résolvent des zones renvoyant une annonce de même
    `id` bien'ici, scrape() ne la retourne qu'une fois. Falsifiable : rouge si
    le `seen` n'est pas partagé entre communes (doublon)."""
    zone_map = {c: _zone_for(c) for c in _METRO_CITIES}
    _install_discover_spy(monkeypatch, zone_map)

    # Même id bien'ici "shared-1" servi via DEUX communes distinctes (zone qui
    # se recouvre). Le `seen` global doit le dédupliquer.
    shared = _make_ad("shared-1", "Marly")
    ads_by_commune = {
        "Marly": [shared],
        "Montigny-Les-Metz": [dict(shared)],  # même id, autre commune ciblée
    }
    _install_fetch_json(monkeypatch, ads_by_commune)

    results = BieniciScraper().scrape()

    expected_id = generate_stable_id(SOURCE_NAME, "shared-1")
    matching = [r for r in results if r.id == expected_id]
    assert len(matching) == 1, (
        "id partagé entre 2 communes retourné %d fois, attendu 1 (seen non "
        "partagé ?) (AC7)" % (len(matching),)
    )


# ===========================================================================
# Phase B (challenge adversarial) — sondes de falsifiabilité et durcissement
# ===========================================================================
# Ces tests verrouillent des invariants que les AC de phase A ne prouvaient pas
# directement, et préviennent des faux-verts (mock-évasion, duplication de la
# liste, seen qui avalerait des ids distincts, exception de résolution de zone).


def test_phase_b_no_real_network_when_mocks_installed(monkeypatch):
    """Sonde mock-évasion (faille signalée en phase A). discover_zone_ids ET
    fetch_json DOIVENT être interceptés au niveau du MODULE bienici. Si un futur
    refactor utilisait un `from scrapers.base import fetch_json` LOCAL à scrape
    (ou un alias) échappant au monkeypatch, ou court-circuitait nos fakes, le
    code retomberait sur `scrapers.base._session.get` (vrai réseau). On le rend
    EXPLOSIF : toute fuite vers le réseau réel lève RuntimeError ici, alors que
    les fakes de module n'y touchent jamais. Falsifiable : rouge si le code
    n'appelle pas discover_zone_ids/fetch_json via le symbole de module."""
    import scrapers.base as base

    def _boom(*a, **k):
        raise RuntimeError(
            "appel réseau réel via scrapers.base._session.get : un symbole "
            "(discover_zone_ids / fetch_json) a échappé au monkeypatch de module"
        )

    monkeypatch.setattr(base._session, "get", _boom)

    zone_map = {c: _zone_for(c) for c in _METRO_CITIES}
    _install_discover_spy(monkeypatch, zone_map)
    ads_by_commune = {c: [_make_ad(f"{c}-1", c)] for c in _METRO_CITIES}
    _install_fetch_json(monkeypatch, ads_by_commune)

    # Si les symboles sont bien interceptés au niveau module, aucun appel à
    # _session.get n'a lieu -> pas de RuntimeError, et on collecte normalement.
    results = BieniciScraper().scrape()
    assert results, "aucune annonce collectée alors que les fakes en servent"


def test_phase_b_communes_is_metro_cities_single_source_of_truth():
    """Anti-duplication (SPEC §3.1 : dupliquer la liste n'est PAS autorisé ;
    source unique = _METRO_CITIES). AC1/AC2 captent un ENSEMBLE d'appels et
    resteraient verts si le dev recopiait littéralement les 11 communes en dur.
    On exige que la liste configurée SOIT _METRO_CITIES (même objet ou égalité
    de séquence ordonnée), pas une copie divergente silencieusement. Falsifiable :
    rouge si le scraper hardcode sa propre liste."""
    from app import market_stats

    configured = list(BieniciScraper.communes)
    assert configured == list(market_stats._METRO_CITIES), (
        "BieniciScraper.communes doit refléter _METRO_CITIES (source unique de "
        "vérité, ordre inclus) ; reçu %r" % (configured,)
    )
    # Garde-fou anti-duplication renforcé : si la liste était recopiée en dur,
    # une modification future de _METRO_CITIES ne s'y refléterait pas. On vérifie
    # qu'aucune commune n'a été oubliée/ajoutée par rapport à la source.
    assert set(configured) == set(market_stats._METRO_CITIES)
    assert len(configured) == len(market_stats._METRO_CITIES), (
        "doublon dans la liste configurée des communes"
    )


def test_phase_b_distinct_ids_per_commune_not_swallowed_by_seen(monkeypatch):
    """Sonde du `seen` global (§point 3) : le seen partagé ne doit dédupliquer
    que les MÊMES ids bien'ici, pas avaler des annonces légitimement distinctes.
    Chaque commune sert un id UNIQUE -> toutes doivent ressortir. Falsifiable :
    rouge si le seen confondait des ids distincts (ou si seen était initialisé
    par commune et perdait la dédup — couvert par AC7, ici le miroir : on prouve
    que le seen ne sur-déduplique pas)."""
    zone_map = {c: _zone_for(c) for c in _METRO_CITIES}
    _install_discover_spy(monkeypatch, zone_map)

    ads_by_commune = {c: [_make_ad(f"{c}-uniq", c)] for c in _METRO_CITIES}
    _install_fetch_json(monkeypatch, ads_by_commune)

    results = BieniciScraper().scrape()

    expected_ids = {
        generate_stable_id(SOURCE_NAME, f"{c}-uniq") for c in _METRO_CITIES
    }
    got_ids = {r.id for r in results}
    assert got_ids == expected_ids, (
        "un id distinct par commune doit ressortir une fois chacun ; "
        "manquants=%r, en trop=%r" % (expected_ids - got_ids, got_ids - expected_ids)
    )


def test_phase_b_seen_initialized_once_across_communes(monkeypatch):
    """Le `seen` est partagé et initialisé UNE seule fois pour tout le run. On
    sert le même id via deux communes ET un id propre à une troisième : le
    partagé sort 1 fois, le propre sort 1 fois (total 2). Si le seen était
    ré-initialisé par commune, le partagé sortirait 2 fois (total 3).
    Falsifiable : rouge sur un seen par-commune."""
    zone_map = {c: _zone_for(c) for c in _METRO_CITIES}
    _install_discover_spy(monkeypatch, zone_map)

    shared = _make_ad("shared-x", "Marly")
    ads_by_commune = {
        "Marly": [shared],
        "Montigny-Les-Metz": [dict(shared)],         # même id, autre commune
        "Woippy": [_make_ad("woippy-only", "Woippy")],  # id propre
    }
    _install_fetch_json(monkeypatch, ads_by_commune)

    results = BieniciScraper().scrape()
    ids = [r.id for r in results]
    shared_id = generate_stable_id(SOURCE_NAME, "shared-x")
    woippy_id = generate_stable_id(SOURCE_NAME, "woippy-only")

    assert ids.count(shared_id) == 1, (
        "id partagé sorti %d fois (seen ré-initialisé par commune ?)"
        % ids.count(shared_id)
    )
    assert ids.count(woippy_id) == 1, "id propre à Woippy manquant ou dupliqué"
    assert len(results) == 2, (
        "attendu 2 listings distincts (1 partagé dédupé + 1 propre), reçu %d"
        % len(results)
    )


def test_phase_b_resolution_exception_residual_risk(monkeypatch):
    """Robustesse skip (§point 4). La SPEC §3.2 ne prévoit le skip que pour un
    retour `[]` ; une EXCEPTION de discover_zone_ids n'est PAS gérée par scrape
    (pas de try/except autour de la résolution). Ce test DOCUMENTE le risque
    résiduel : si une commune fait lever discover_zone_ids, la collecte des
    communes SUIVANTES est perdue. C'est conforme à la spec (seul `[]` est
    spécifié) ; on fige le comportement réel pour qu'un changement soit visible.

    NB : ce n'est PAS un AC de la spec. On ne durcit pas le code (hors périmètre) ;
    on consigne la limite. Si la collecte prod montre des exceptions de suggest,
    remonter pour un try/except par commune."""
    zone_map = {c: _zone_for(c) for c in _METRO_CITIES}
    calls = []

    # Trouve une commune NON terminale pour prouver que les suivantes sont
    # perdues si une exception remonte (ordre = _METRO_CITIES, trié).
    boom_commune = _METRO_CITIES[0]

    def fake_discover(city_name):
        calls.append(city_name)
        if city_name == boom_commune:
            raise RuntimeError("suggest indisponible")
        return list(zone_map.get(city_name, []))

    monkeypatch.setattr(bienici, "discover_zone_ids", fake_discover)
    _install_fetch_json(monkeypatch, ads_by_commune={})

    # Comportement RÉEL observé (conforme spec : exception non spécifiée donc
    # non rattrapée). Si un dev ajoute un try/except par commune, ce test devra
    # être ré-arbitré par le testeur (pas « optimisé » par le dev) — leçon
    # atelier sur la propriété de l'oracle.
    with pytest.raises(RuntimeError):
        BieniciScraper().scrape()
    # La commune qui lève est bien la première interrogée (aucune suivante
    # n'a pu compléter) : preuve que le risque est réel, pas masqué.
    assert calls == [boom_commune], (
        "comportement attendu : l'exception remonte dès la 1re commune, "
        "interrompant les suivantes ; calls=%r" % (calls,)
    )


def test_phase_b_metz_still_collected_no_regression(monkeypatch):
    """Anti-régression (§point 5) : Metz reste dans la liste ET est collecté
    (la collecte Metz d'origine ne doit pas être perdue par l'itération
    multi-communes). Falsifiable : rouge si Metz disparaît de communes ou si
    aucune annonce Metz ne ressort."""
    assert "Metz" in BieniciScraper.communes, "Metz doit rester ciblée"

    zone_map = {c: _zone_for(c) for c in _METRO_CITIES}
    _install_discover_spy(monkeypatch, zone_map)
    ads_by_commune = {"Metz": [_make_ad("metz-reg", "Metz")]}
    _install_fetch_json(monkeypatch, ads_by_commune)

    results = BieniciScraper().scrape()
    metz_id = generate_stable_id(SOURCE_NAME, "metz-reg")
    assert any(r.id == metz_id for r in results), (
        "l'annonce Metz n'a pas été collectée (régression collecte Metz)"
    )
    assert canonical_city("Metz") in {r.city for r in results}
