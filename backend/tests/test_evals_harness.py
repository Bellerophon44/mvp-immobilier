"""Tests-first du chantier evals-harness (docs/specs/evals-harness-SPEC.md).

Couvre les AC verifiables SANS appel LLM, sans reseau et sans secret :
- structure et separation des suites (AC1-AC6) ;
- garde d'environnement du conftest d'evals (AC7-AC11), testee dynamiquement
  par sous-processus pytest (la garde echoue AVANT tout appel reseau) et
  statiquement par inspection du source (jamais d'import de conftest sous un
  second nom de module — lecon cross-agence-inc1) ;
- cas synthetique issue #80 : tokens requis/interdits (AC12-AC13), point
  d'appel LLM unique et assertions du module d'eval par inspection AST
  (AC14-AC17, le comportement runtime appartient a la suite evals payante) ;
- tests deterministes gratuits (AC19-AC21) : presence et statuts d'execution
  reels ;
- workflow CI evals.yml (AC22-AC26) et documentation (AC27-AC28).

Etat post-fix #80 (chantier fix-issue-80, push 2, AC28-AC32 de sa spec) : les
oracles qui figeaient les marqueurs xfail (etat pre-fix) sont bascules — les
tests de regression A et B (evals) et le test deterministe `rez-de-chaussée`
sont exiges SANS marqueur xfail (bloquants), et l'execution reelle du fichier
deterministe ne doit plus produire ni xfailed ni xpassed.

AC18 (preuve de reproduction XFAIL dans le run CI de la PR) est un AC de
process non automatisable ici : il est couvert indirectement par l'exigence
README (AC27) et la verification de provenance du docstring (§4.3).
"""

import ast
import configparser
import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
EVALS_DIR = BACKEND / "evals"
EVALS_CONFTEST = EVALS_DIR / "conftest.py"
CASE_FILE = EVALS_DIR / "cases" / "issue_80.txt"
EVAL_MODULE = EVALS_DIR / "test_eval_issue_80.py"
PYTEST_INI = BACKEND / "pytest.ini"
ISOLATION_FILE = BACKEND / "tests" / "test_evals_isolation.py"
DETERMINISTIC_FILE = BACKEND / "tests" / "test_issue_80_deterministic.py"
EVALS_WORKFLOW = ROOT / ".github" / "workflows" / "evals.yml"
TEST_WORKFLOW = ROOT / ".github" / "workflows" / "test.yml"
PILOTES_README = ROOT / "docs" / "pilotes" / "README.md"
BACKEND_CLAUDE = BACKEND / "CLAUDE.md"
CONTEXT_MD = ROOT / "CONTEXT.md"

# Cle factice ABSENTE de la liste de refus du conftest d'evals (§3.3) : permet
# les collectes/probes sans declencher la garde, sans etre une vraie cle.
_PROBE_KEY = "sk-probe-collecte-pas-une-vraie-cle"
_KEEP = object()


def _read(path: Path) -> str:
    assert path.is_file(), f"Fichier attendu absent : {path}"
    return path.read_text(encoding="utf-8")


def _run_pytest(args, key=_KEEP, timeout=300):
    """Lance pytest en sous-processus depuis backend/ (jamais d'import direct
    des conftest : lecon du double-import). Le pid du sous-processus differe du
    parent, donc le bootstrap DB jetable du conftest reste isole."""
    env = os.environ.copy()
    env.pop("MVP_TEST_DB_BOOTSTRAPPED", None)
    env.pop("PYTEST_ADDOPTS", None)
    if key is None:
        env.pop("OPENAI_API_KEY", None)
    elif key is not _KEEP:
        env["OPENAI_API_KEY"] = key
    return subprocess.run(
        [sys.executable, "-m", "pytest", *args],
        cwd=str(BACKEND),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _nodeids(proc) -> list:
    return [l.strip() for l in proc.stdout.splitlines() if "::" in l]


def _is_evals_item(line: str) -> bool:
    norm = line.replace("\\", "/")
    return norm.startswith("evals/") or "/evals/" in norm


# ---------------------------------------------------------------------------
# Helpers AST (inspection statique des fichiers produits, sans les importer)
# ---------------------------------------------------------------------------

def _dotted(node) -> str:
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def _xfail_marks(func_node) -> list:
    """Liste des decorateurs xfail d'une fonction : [{'strict':..., 'reason':...}]."""
    marks = []
    for dec in func_node.decorator_list:
        target = dec.func if isinstance(dec, ast.Call) else dec
        if _dotted(target).endswith("xfail"):
            info = {"strict": None, "reason": None}
            if isinstance(dec, ast.Call):
                for kw in dec.keywords:
                    if kw.arg in ("strict", "reason") and isinstance(kw.value, ast.Constant):
                        info[kw.arg] = kw.value.value
            marks.append(info)
    return marks


def _fixture_kwargs(func_node):
    """Kwargs constants du decorateur @pytest.fixture, ou None si pas fixture."""
    for dec in func_node.decorator_list:
        target = dec.func if isinstance(dec, ast.Call) else dec
        if _dotted(target).endswith("fixture"):
            kwargs = {}
            if isinstance(dec, ast.Call):
                for kw in dec.keywords:
                    if isinstance(kw.value, ast.Constant):
                        kwargs[kw.arg] = kw.value.value
            return kwargs
    return None


def _functions(src: str):
    tree = ast.parse(src)
    return [
        n for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def _segment(src: str, node) -> str:
    return ast.get_source_segment(src, node) or ""


# ===========================================================================
# Structure et separation des suites (AC1-AC6)
# ===========================================================================

def test_ac1_pytest_ini_testpaths_tests():
    """AC1 : backend/pytest.ini existe, section [pytest], testpaths = tests."""
    assert PYTEST_INI.is_file(), "backend/pytest.ini absent (AC1)"
    cfg = configparser.ConfigParser()
    cfg.read(PYTEST_INI, encoding="utf-8")
    assert cfg.has_section("pytest"), "section [pytest] absente de pytest.ini"
    assert cfg.get("pytest", "testpaths", fallback="").strip() == "tests", (
        "pytest.ini doit declarer exactement `testpaths = tests` (AC1)"
    )


@pytest.fixture(scope="module")
def collecte_defaut():
    return _run_pytest(["--collect-only", "-q"])


@pytest.fixture(scope="module")
def collecte_tests():
    return _run_pytest(["--collect-only", "-q", "tests"])


def test_ac2_collecte_par_defaut_exclut_evals(collecte_defaut):
    """AC2 : `pytest --collect-only -q` sans argument ne liste aucun item
    evals/, ALORS QUE backend/evals/test_eval_issue_80.py existe (sinon le
    test serait vert par vacuite)."""
    assert EVAL_MODULE.is_file(), (
        "backend/evals/test_eval_issue_80.py absent : l'exclusion de la "
        "collecte serait verte par vacuite (AC2)"
    )
    ids = _nodeids(collecte_defaut)
    assert ids, f"Collecte par defaut vide ou en erreur :\n{collecte_defaut.stdout}\n{collecte_defaut.stderr}"
    fuites = [l for l in ids if _is_evals_item(l)]
    assert not fuites, f"Items evals/ collectes par la suite gratuite : {fuites}"


def test_ac3_oracle_isolation_present_dans_tests():
    """AC3 (statique) : tests/test_evals_isolation.py existe et porte l'oracle
    dynamique sur les items de la session courante + le test statique de
    pytest.ini (spec §7.1)."""
    src = _read(ISOLATION_FILE)
    assert "request.session.items" in src, (
        "test_evals_isolation.py doit inspecter request.session.items (AC3)"
    )
    assert "evals" in src, "l'oracle doit asserter l'absence du segment `evals`"
    assert "testpaths" in src, (
        "test_evals_isolation.py doit aussi verifier statiquement "
        "`testpaths = tests` dans pytest.ini (spec §7.1)"
    )


def test_ac3_pytest_ini_est_le_mecanisme_effectif(tmp_path):
    """AC3 (dynamique) : sans le testpaths de pytest.ini (config neutralisee
    via -c), la collecte par defaut ramasse de nouveau evals/ — preuve que
    l'isolation repose sur pytest.ini et que sa suppression serait detectee."""
    assert EVAL_MODULE.is_file(), (
        "backend/evals/test_eval_issue_80.py absent : impossible de prouver "
        "que pytest.ini est le mecanisme d'isolation (AC3)"
    )
    neutre = tmp_path / "neutre.ini"
    neutre.write_text("[pytest]\n", encoding="utf-8")
    proc = _run_pytest(
        ["--collect-only", "-q", "-c", str(neutre), "--rootdir", str(BACKEND), "."],
        key=_PROBE_KEY,
    )
    ids = _nodeids(proc)
    assert any(_is_evals_item(l) for l in ids), (
        "Config neutralisee : evals/ devrait etre collecte (sinon l'isolation "
        f"ne vient pas de pytest.ini).\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )


def test_ac4_collecte_defaut_identique_a_collecte_tests(collecte_defaut, collecte_tests):
    """AC4 : la collecte par defaut et la collecte explicite de tests/ listent
    exactement les memes items (non-regression de la suite gratuite)."""
    assert EVAL_MODULE.is_file(), (
        "backend/evals/test_eval_issue_80.py absent : la comparaison serait "
        "verte par vacuite (AC4)"
    )
    assert collecte_defaut.returncode == 0, collecte_defaut.stdout + collecte_defaut.stderr
    assert collecte_tests.returncode == 0, collecte_tests.stdout + collecte_tests.stderr
    assert set(_nodeids(collecte_defaut)) == set(_nodeids(collecte_tests)), (
        "La collecte par defaut differe de `pytest --collect-only -q tests` (AC4)"
    )


def test_ac5_collecte_explicite_evals_uniquement():
    """AC5 : `pytest evals --collect-only -q` ne collecte que des items sous
    evals/ (cle factice hors liste de refus : la garde ne doit pas bloquer)."""
    proc = _run_pytest(["evals", "--collect-only", "-q"], key=_PROBE_KEY)
    assert proc.returncode == 0, (
        f"Collecte de evals/ en echec (rc={proc.returncode}) :\n"
        f"{proc.stdout}\n{proc.stderr}"
    )
    ids = _nodeids(proc)
    assert ids, "Aucun item collecte sous evals/ (AC5)"
    hors_evals = [l for l in ids if not _is_evals_item(l)]
    assert not hors_evals, f"Items hors evals/ collectes : {hors_evals}"


def test_ac6_test_yml_strictement_inchange():
    """AC6 : .github/workflows/test.yml est identique a son etat avant
    chantier (empreinte figee) et ne mentionne pas evals."""
    contenu = TEST_WORKFLOW.read_bytes()
    empreinte = hashlib.sha256(contenu).hexdigest()
    assert empreinte == (
        "65d638e9846b2117f2899733aabe2d82ee186ea3ee5ea3ede39ac3b5b539d799"
    ), "test.yml a ete modifie par le chantier (AC6 : git diff doit etre vide)"
    assert "evals" not in contenu.decode("utf-8")


# ===========================================================================
# Conftest d'evals : garde d'environnement (AC7-AC11)
# ===========================================================================

def _assert_echec_explicite(proc):
    sortie = proc.stdout + proc.stderr
    assert proc.returncode != 0, (
        f"`pytest evals` aurait du echouer (rc={proc.returncode}) :\n{sortie}"
    )
    assert "OPENAI_API_KEY" in sortie, (
        f"L'echec doit etre explicite et mentionner OPENAI_API_KEY :\n{sortie}"
    )
    assert not re.search(r"\b[1-9]\d* passed", sortie), (
        f"Aucun test ne doit passer sans cle valide (faux vert) :\n{sortie}"
    )


def test_ac7_garde_cle_absente():
    """AC7 : OPENAI_API_KEY non definie -> code retour non nul et message
    explicite mentionnant OPENAI_API_KEY, sans aucun test vert."""
    assert EVALS_DIR.is_dir(), "backend/evals/ absent (AC7)"
    _assert_echec_explicite(_run_pytest(["evals"], key=None))


@pytest.mark.parametrize(
    "placeholder",
    ["", "test-key-not-real", "test-key-not-used"],
    ids=["vide", "placeholder-test-yml", "placeholder-conftest-tests"],
)
def test_ac8_garde_cle_placeholder(placeholder):
    """AC8 : cle vide ou placeholder connue -> meme echec explicite qu'AC7.
    Discriminant : une erreur d'authentification OpenAI ne contiendrait pas la
    chaine OPENAI_API_KEY, seule la garde du conftest la produit."""
    assert EVALS_DIR.is_dir(), "backend/evals/ absent (AC8)"
    _assert_echec_explicite(_run_pytest(["evals"], key=placeholder))


@pytest.mark.parametrize(
    "cle_bord",
    ["   ", "\t", " test-key-not-real ", "test-key-not-used "],
    ids=["espaces", "tabulation", "placeholder-padde-1", "placeholder-padde-2"],
)
def test_ac8_durci_garde_cle_blancs_et_placeholders_paddes(cle_bord):
    """AC8 durci (phase B) : une cle composee uniquement de blancs, ou un
    placeholder entoure d'espaces, doit etre refusee comme la chaine vide.
    Le step workflow `[ -z "$OPENAI_API_KEY" ]` laisse passer une valeur
    d'espaces : la garde du conftest est la derniere ligne de defense — elle
    doit normaliser (strip) avant comparaison."""
    assert EVALS_DIR.is_dir(), "backend/evals/ absent (AC8 durci)"
    _assert_echec_explicite(_run_pytest(["evals"], key=cle_bord))


def test_ac9_conftest_evals_database_path_force_avant_imports_app():
    """AC9 (statique) : evals/conftest.py force os.environ["DATABASE_PATH"]
    (affectation directe, suffixe pid, jamais setdefault) avant tout import
    app.*/db.*, et porte la garde de cle (placeholders refuses)."""
    src = _read(EVALS_CONFTEST)
    m = re.search(r"os\.environ\[\s*[\"']DATABASE_PATH[\"']\s*\]\s*=", src)
    assert m, "Affectation directe os.environ[\"DATABASE_PATH\"] = ... absente (AC9)"
    assert not re.search(r"setdefault\(\s*[\"']DATABASE_PATH", src), (
        "setdefault interdit sur DATABASE_PATH (lecon 9.7 durcie)"
    )
    assert "getpid" in src, "Le fichier jetable doit etre suffixe par le pid (AC9)"

    # La garde refuse les placeholders des deux suites gratuites (§3.3).
    assert "OPENAI_API_KEY" in src
    assert "test-key-not-real" in src, "placeholder de test.yml non refuse (AC8/AC9)"
    assert "test-key-not-used" in src, "placeholder de tests/conftest.py non refuse (AC8/AC9)"

    # Ordonnancement : l'affectation DATABASE_PATH precede tout import
    # top-level de app.* / db.* (la chaine d'import de analysis.py touche db/).
    ligne_affectation = src[: m.start()].count("\n") + 1
    tree = ast.parse(src)
    lignes_imports = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in ("app", "db"):
                    lignes_imports.append(node.lineno)
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in ("app", "db"):
                lignes_imports.append(node.lineno)
    if lignes_imports:
        assert ligne_affectation < min(lignes_imports), (
            "DATABASE_PATH doit etre force AVANT tout import app.*/db.* (AC9)"
        )


def test_ac10_reset_cache_llm_fixture_autouse_session():
    """AC10 : evals/conftest.py definit une fixture autouse scope=session qui
    vide llm_semantic._CACHE au demarrage (lecon photo-evidence)."""
    src = _read(EVALS_CONFTEST)
    candidates = [
        f for f in _functions(src)
        if (_fixture_kwargs(f) or {}).get("scope") == "session"
        and (_fixture_kwargs(f) or {}).get("autouse") is True
        and "_CACHE.clear" in _segment(src, f)
    ]
    assert candidates, (
        "Fixture autouse scope=\"session\" executant llm_semantic._CACHE.clear() "
        "absente de evals/conftest.py (AC10)"
    )


def test_ac11_aucun_mock_ni_override_config_dans_evals():
    """AC11 : aucun mock de facade ni override de la config LLM prod dans
    backend/evals/ (equivalent du grep -rn de la spec)."""
    assert EVALS_DIR.is_dir(), "backend/evals/ absent (AC11)"
    fichiers = [p for p in EVALS_DIR.rglob("*") if p.is_file() and p.suffix in (".py", ".txt", ".ini", ".cfg", ".toml")]
    assert fichiers, "backend/evals/ vide (AC11)"
    interdits_litteraux = ("unittest.mock", "MagicMock", "monkeypatch", "OpenAI(")
    for path in fichiers:
        texte = path.read_text(encoding="utf-8")
        for token in interdits_litteraux:
            assert token not in texte, f"{path} contient `{token}` (AC11)"
        assert not re.search(r"\b(TEMPERATURE|MODEL_NAME)\s*=", texte), (
            f"{path} reassigne TEMPERATURE/MODEL_NAME (config prod intouchable, AC11)"
        )


# ===========================================================================
# Cas synthetique issue #80 (AC12-AC14 + provenance §4.3)
# ===========================================================================

def _texte_cas() -> str:
    # Normalisation des espaces insecables : equivalence visuelle assumee pour
    # les sous-chaines avec espaces ("565 000 €", "282 m²", "4 chambres").
    return _read(CASE_FILE).replace(" ", " ").replace(" ", " ")


def test_ac12_annonce_synthetique_tokens_requis():
    """AC12 : cases/issue_80.txt, 400-1500 caracteres, tous les declencheurs
    presents (insensible a la casse)."""
    texte = _texte_cas()
    longueur = len(texte.strip())
    assert 400 <= longueur <= 1500, f"Longueur {longueur} hors bornes [400, 1500] (AC12)"
    bas = texte.casefold()
    requis = [
        "villa", "plain-pied", "maison individuelle", "282 m²", "dpe",
        "2006", "suite parentale", "4 chambres", "565 000 €", "marly",
    ]
    manquants = [t for t in requis if t not in bas]
    assert not manquants, f"Declencheurs absents de issue_80.txt : {manquants} (AC12)"
    assert "environ 282" not in bas, "La surface doit etre exacte, sans `environ` (§4.1)"


def test_ac13_annonce_synthetique_tokens_interdits():
    """AC13 : aucun token interdit (copro/syndic/charges : le symptome 2 doit
    venir du LLM ; http/www./@ : pas d'URL ni d'email)."""
    bas = _texte_cas().casefold()
    interdits = ["copropriété", "copropriete", "syndic", "charges", "http", "www.", "@"]
    presents = [t for t in interdits if t in bas]
    assert not presents, f"Tokens interdits presents dans issue_80.txt : {presents} (AC13)"


def test_ac14_un_seul_point_appel_analyze_semantic():
    """AC14 : analyze_semantic n'est appele qu'a UN endroit dans evals/ : la
    fixture scope=\"module\" du cas (1 appel LLM par cas et par run)."""
    assert EVALS_DIR.is_dir(), "backend/evals/ absent (AC14)"
    appels = []
    fixtures_module_appelantes = []
    for path in EVALS_DIR.rglob("*.py"):
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _dotted(node.func).endswith("analyze_semantic"):
                appels.append(f"{path}:{node.lineno}")
        for func in _functions(src):
            kwargs = _fixture_kwargs(func)
            if kwargs is not None and kwargs.get("scope") == "module" \
                    and "analyze_semantic(" in _segment(src, func):
                fixtures_module_appelantes.append(func.name)
    assert len(appels) == 1, (
        f"analyze_semantic doit avoir exactement 1 site d'appel dans evals/, "
        f"trouve {len(appels)} : {appels} (AC14)"
    )
    assert fixtures_module_appelantes, (
        "Le site d'appel unique doit etre une fixture scope=\"module\" (AC14)"
    )


def test_provenance_docstring_cas_synthetique():
    """§4.3 (support AC18) : le docstring du module d'eval reference l'issue
    #80 et rappelle que le texte est synthetique (regle CONTEXT §11.3)."""
    src = _read(EVAL_MODULE)
    doc = ast.get_docstring(ast.parse(src)) or ""
    assert "#80" in doc, "Le docstring doit referencer l'issue #80 (§4.3)"
    assert "synth" in doc.casefold(), (
        "Le docstring doit rappeler que l'annonce est synthetique (§4.3 / §11.3)"
    )


# ===========================================================================
# Cas #80 : assertions du module d'eval, par inspection AST (AC15-AC17)
# ===========================================================================

def test_ac15_assertions_bloquantes_sans_xfail():
    """AC15 : les assertions de sanity d'extraction (§5.2) existent dans des
    tests SANS marqueur xfail (pouvoir bloquant du harnais des le jour 1)."""
    src = _read(EVAL_MODULE)
    corps_bloquants = "\n".join(
        _segment(src, f)
        for f in _functions(src)
        if f.name.startswith("test_") and not _xfail_marks(f)
    )
    assert corps_bloquants, "Aucun test sans xfail dans test_eval_issue_80.py (AC15)"
    attendus = {
        "property_type == \"maison\"": r"property_type[^\n]*==\s*[\"']maison[\"']",
        "surface_m2 == 282.0": r"surface_m2[^\n]*282(\.0)?",
        "dpe == \"C\"": r"dpe[^\n]*==\s*[\"']C[\"']",
        "construction_year == 2006": r"construction_year[^\n]*2006",
        "price_total == 565000.0": r"price_total[^\n]*565[_ ]?000(\.0)?",
        "len(questions) >= 1": r"len\([^)\n]*questions[^)\n]*\)\s*>=\s*1",
    }
    manquantes = [k for k, pattern in attendus.items() if not re.search(pattern, corps_bloquants)]
    assert not manquantes, (
        f"Assertions bloquantes absentes (ou marquees xfail) : {manquantes} (AC15)"
    )


def test_ac16_regression_a_rendu_rez_de_chaussee_bloquant():
    """AC16, bascule AC28 (fix-issue-80 push 2) : la regression A (rendu
    compose sur l'extraction reelle, sans `rez-de-chaussée`) est exigee SANS
    aucun marqueur xfail (bloquante depuis le fix), compose toujours
    _criteria_signal(_amenity_attrs(listing)), reutilise la fixture (pas
    d'appel LLM supplementaire) et n'asserte pas `floor`. Echoue si un xfail
    est reintroduit."""
    src = _read(EVAL_MODULE)
    candidats = [
        f for f in _functions(src)
        if f.name.startswith("test_")
        and "_criteria_signal" in _segment(src, f)
        and "_amenity_attrs" in _segment(src, f)
        and "rez-de-chaussée" in _segment(src, f)
    ]
    assert candidats, (
        "Test de regression A absent : test composant "
        "_criteria_signal(_amenity_attrs(listing)) et assertant l'absence de "
        "`rez-de-chaussée` (AC16/AC28)"
    )
    for f in candidats:
        assert not _xfail_marks(f), (
            f"{f.name} : marqueur xfail reintroduit sur la regression A — fix "
            "#80 livre, le test doit rester bloquant (AC28)"
        )
        corps = _segment(src, f)
        assert "analyze_semantic(" not in corps, (
            f"{f.name} : la regression A ne doit pas declencher d'appel LLM "
            "supplementaire (reutiliser la fixture, AC16)"
        )
        assert not re.search(r"assert[^\n]*floor", corps), (
            f"{f.name} : pas d'assertion sur la valeur de floor (design du fix "
            "non fige, AC16)"
        )


def test_ac17_regression_b_questions_copropriete_bloquant():
    """AC17, bascule AC29 (fix-issue-80 push 2) : la regression B (aucune
    question copropriete/syndic sur maison individuelle) est exigee SANS
    marqueur xfail (bloquante depuis le fix)."""
    src = _read(EVAL_MODULE)
    candidats = [
        f for f in _functions(src)
        if f.name.startswith("test_")
        and "questions" in _segment(src, f)
        and "copropri" in _segment(src, f).casefold()
        and "syndic" in _segment(src, f).casefold()
    ]
    assert candidats, (
        "Test de regression B absent : test assertant qu'aucune entree de "
        "questions ne contient copropriété/copropriete/syndic (AC17/AC29)"
    )
    for f in candidats:
        assert not _xfail_marks(f), (
            f"{f.name} : marqueur xfail reintroduit sur la regression B — fix "
            "#80 livre, le test doit rester bloquant (AC29)"
        )


def test_phase_b_fixtures_des_xfail_partagees_avec_un_test_bloquant():
    """Durcissement phase B (anti faux-vert structurel) : pytest convertit en
    XFAIL silencieux (exit 0) l'ERREUR DE SETUP d'un test marque xfail — une
    fixture module qui leve ne produit PAS d'error sur ces tests (verifie par
    sonde : fixture raise + xfail(strict=False) -> `1 xfailed`, rc=0).

    Le harnais n'est donc protege que si CHAQUE fixture consommee par un test
    xfail est aussi consommee par au moins un test bloquant (sans xfail) : la
    meme erreur de fixture y devient alors un ERROR qui met le job au rouge.

    Bascule AC30 (fix-issue-80 push 2) : le fix #80 etant livre, le module
    d'eval ne porte plus aucun xfail — la propriete devient CONDITIONNELLE
    (verifiee pour tout futur test xfail, sans en exiger l'existence) ;
    l'exigence d'au moins un test bloquant est conservee."""
    src = _read(EVAL_MODULE)
    tests_xfail = []
    tests_bloquants = []
    for f in _functions(src):
        if not f.name.startswith("test_"):
            continue
        params = {a.arg for a in f.args.args if a.arg != "self"}
        if _xfail_marks(f):
            tests_xfail.append((f.name, params))
        else:
            tests_bloquants.append((f.name, params))
    assert tests_bloquants, "Aucun test bloquant dans le module d'eval (AC15)"
    params_bloquants = set().union(*(p for _, p in tests_bloquants))
    for nom, params in tests_xfail:
        orphelines = params - params_bloquants
        assert not orphelines, (
            f"{nom} consomme des fixtures qu'aucun test bloquant ne partage "
            f"({sorted(orphelines)}) : une erreur de cette fixture serait "
            "convertie en XFAIL silencieux (exit 0) au lieu de mettre le job "
            "au rouge (piege pytest setup-error + xfail)"
        )


# ===========================================================================
# Tests deterministes gratuits (AC19-AC21)
# ===========================================================================

def test_ac19_statique_bloquant_rez_de_chaussee():
    """AC19, bascule AC31 (fix-issue-80 push 2) :
    tests/test_issue_80_deterministic.py porte le test deterministe du rendu
    `rez-de-chaussée` (maison, floor=0, _criteria_signal) SANS marqueur xfail
    — l'ex-memoire executable du fix est devenue bloquante."""
    src = _read(DETERMINISTIC_FILE)
    candidats = []
    for f in _functions(src):
        if not f.name.startswith("test_"):
            continue
        corps = _segment(src, f)
        if (
            "rez-de-chaussée" in corps
            and "_criteria_signal" in corps
            and re.search(r"floor[\"']?\s*[:=]\s*0", corps)
            and "maison" in corps.casefold()
        ):
            candidats.append((f, corps))
    assert candidats, (
        "Test deterministe sur le rendu `rez-de-chaussée` (maison, floor=0, "
        "_criteria_signal) absent du fichier deterministe (AC19/AC31)"
    )
    for f, corps in candidats:
        assert not _xfail_marks(f), (
            f"{f.name} : marqueur xfail reintroduit — fix #80 livre, le test "
            "deterministe doit rester bloquant (AC31)"
        )


def test_ac20_statique_garde_amenity_actions_sans_xfail():
    """AC20 (statique) : le meme fichier porte un test PASSANT (sans xfail)
    verrouillant que _amenity_actions (maison, condo_fees=None) ne genere
    aucune question copropriete/syndic."""
    src = _read(DETERMINISTIC_FILE)
    candidats = [
        f for f in _functions(src)
        if f.name.startswith("test_")
        and not _xfail_marks(f)
        and "_amenity_actions" in _segment(src, f)
        and "copropri" in _segment(src, f).casefold()
        and "syndic" in _segment(src, f).casefold()
    ]
    assert candidats, (
        "Garde passante sur _amenity_actions (copropriete/syndic) absente ou "
        "marquee xfail (AC20)"
    )
    assert any(
        re.search(r"condo_fees[\"']?\s*[:=]\s*None", _segment(src, f)) for f in candidats
    ), "Le listing de la garde doit poser condo_fees=None (AC20)"


def test_ac19_ac20_ac21_statuts_reels_bloquants_et_passants():
    """AC19/AC20/AC21 (dynamique), bascule AC32 (fix-issue-80 push 2) :
    execution reelle du fichier deterministe sous la cle factice de test.yml
    (aucun reseau possible : un appel OpenAI avec cette cle echouerait) ->
    returncode 0, au moins 1 passed, AUCUN xfailed (fix livre : plus aucune
    regression attendue), aucun xpassed, aucun failed."""
    assert DETERMINISTIC_FILE.is_file(), (
        "tests/test_issue_80_deterministic.py absent (AC19/AC20/AC21)"
    )
    proc = _run_pytest(
        ["tests/test_issue_80_deterministic.py", "-q", "-rxX"],
        key="test-key-not-real",
    )
    sortie = proc.stdout + proc.stderr
    assert proc.returncode == 0, f"La suite deterministe doit etre verte (AC32) :\n{sortie}"
    assert re.search(r"\b[1-9]\d* passed", sortie), (
        f"Au moins un test passant attendu (garde AC20) :\n{sortie}"
    )
    assert "xfailed" not in sortie, (
        f"XFAIL inattendu : le fix #80 est livre, aucun marqueur xfail ne doit "
        f"subsister dans le fichier deterministe (AC32) :\n{sortie}"
    )
    assert "xpassed" not in sortie, (
        f"XPASS inattendu : aucun marqueur xfail ne doit subsister (AC32) :\n{sortie}"
    )
    assert not re.search(r"\b[1-9]\d* failed", sortie), (
        f"Aucun echec sec attendu dans la suite gratuite (AC32) :\n{sortie}"
    )


# ===========================================================================
# Workflow CI evals.yml (AC22-AC26)
# ===========================================================================

def _yaml_list_items(texte: str, cle: str) -> list:
    """Items `- ...` du premier bloc liste suivant `cle:` (parse textuel : pas
    de dependance yaml, suffisant pour un workflow plat)."""
    items = []
    dans_bloc = False
    for ligne in texte.splitlines():
        if re.match(rf"\s*{re.escape(cle)}:\s*$", ligne):
            dans_bloc = True
            continue
        if dans_bloc:
            m = re.match(r"\s*-\s*(.+?)\s*$", ligne)
            if m:
                items.append(m.group(1).strip("\"'"))
            elif ligne.strip():
                break
    return items


def test_ac22_declencheurs_paths_exacts():
    """AC22 : pull_request avec paths EXACTEMENT les 6 entrees de la spec,
    plus workflow_dispatch ; jamais pull_request_target ni backend/**."""
    texte = _read(EVALS_WORKFLOW)
    assert "pull_request_target" not in texte, "pull_request_target interdit (exfiltration de secret, AC22)"
    assert "pull_request:" in texte
    assert "workflow_dispatch" in texte
    assert "backend/**" not in texte, "paths backend/** interdit (budget, AC22)"
    attendus = {
        "backend/app/llm_semantic.py",
        "backend/app/analysis.py",
        "backend/app/market_stats.py",
        "backend/app/scoring.py",
        "backend/evals/**",
        ".github/workflows/evals.yml",
    }
    paths = set(_yaml_list_items(texte, "paths"))
    assert paths == attendus, (
        f"paths du declencheur != spec (AC22).\nAttendus : {sorted(attendus)}\n"
        f"Trouves : {sorted(paths)}"
    )


def test_ac23_permissions_concurrency_timeout():
    """AC23 : permissions minimales, concurrency par ref avec annulation,
    timeout 10 minutes."""
    texte = _read(EVALS_WORKFLOW)
    assert re.search(r"permissions:", texte)
    assert re.search(r"contents:\s*read", texte)
    assert re.search(r"pull-requests:\s*write", texte)
    assert re.search(r"concurrency:", texte)
    assert re.search(r"group:\s*\S*\$\{\{\s*github\.ref\s*\}\}", texte), (
        "concurrency.group doit etre groupe par github.ref (AC23)"
    )
    assert re.search(r"cancel-in-progress:\s*true", texte)
    assert re.search(r"timeout-minutes:\s*10\b", texte)


def test_ac24_garde_secret_avant_pytest_sans_fuite():
    """AC24 : un step AVANT pytest echoue (exit 1) avec un message mentionnant
    OPENAI_API_KEY quand le secret est vide ; la valeur du secret n'est jamais
    affichee."""
    texte = _read(EVALS_WORKFLOW)
    pos_pytest = texte.find("pytest evals")
    assert pos_pytest != -1, "Commande pytest evals absente du workflow (AC25)"
    pos_garde = texte.find("secrets.OPENAI_API_KEY")
    assert pos_garde != -1, "Reference au secret OPENAI_API_KEY absente (AC24)"
    assert pos_garde < pos_pytest, "La garde du secret doit preceder le step pytest (AC24)"
    positions_exit = [m.start() for m in re.finditer(r"exit 1", texte)]
    assert any(p < pos_pytest for p in positions_exit), (
        "La garde doit faire `exit 1` avant le step pytest (AC24)"
    )
    assert re.search(r"(echo|printf)[^\n]*OPENAI_API_KEY", texte), (
        "Message explicite mentionnant OPENAI_API_KEY attendu (AC24)"
    )
    for ligne in texte.splitlines():
        if re.search(r"\b(echo|printf)\b", ligne):
            assert not re.search(r"\$\{\{\s*secrets\.OPENAI_API_KEY\s*\}\}", ligne), (
                f"La valeur du secret ne doit jamais etre affichee : {ligne.strip()} (AC24)"
            )


def test_ac25_commande_pytest_et_statut_bloquant():
    """AC25 : pytest en working-directory backend, flags -q -rxX --tb=short,
    sortie capturee (tee), continue-on-error + step final qui met le job au
    rouge si l'outcome pytest est failure."""
    texte = _read(EVALS_WORKFLOW)
    assert re.search(r"working-directory:\s*backend", texte)
    ligne_cmd = next(
        (l for l in texte.splitlines() if "pytest evals" in l), ""
    )
    assert ligne_cmd, "Commande `python -m pytest evals ...` absente (AC25)"
    for flag in ("python -m pytest evals", "-q", "-rxX", "--tb=short"):
        assert flag in ligne_cmd, f"Flag/commande manquant dans le step pytest : {flag} (AC25)"
    assert "tee" in texte, "Sortie pytest non capturee (tee attendu pour le rapport, AC25)"
    assert re.search(r"continue-on-error:\s*true", texte), (
        "continue-on-error attendu pour poster le rapport avant l'echec (AC25)"
    )
    assert re.search(r"outcome\s*==\s*['\"]failure['\"]", texte), (
        "Step final conditionne a l'outcome failure du step pytest absent (AC25)"
    )
    pos_pytest = texte.find("pytest evals")
    assert any(m.start() > pos_pytest for m in re.finditer(r"exit 1", texte)), (
        "Le step final bloquant (`exit 1` apres pytest) est absent (AC25)"
    )


def test_ac26_commentaire_pr_collant():
    """AC26 : commentaire de PR collant via actions/github-script, marqueur
    <!-- evals -->, if: always(), tronque a 60000 caracteres."""
    texte = _read(EVALS_WORKFLOW)
    assert "actions/github-script" in texte
    assert "<!-- evals -->" in texte, "Marqueur HTML du commentaire collant absent (AC26)"
    assert "always()" in texte
    assert re.search(r"event_name\s*==\s*['\"]pull_request['\"]", texte), (
        "Le commentaire ne doit etre poste que sur pull_request (AC26)"
    )
    assert "60000" in texte, "Troncature a 60000 caracteres absente (AC26)"


# ===========================================================================
# Documentation et process (AC27-AC28)
# ===========================================================================

def test_ac27_readme_pilotes_process_issue_vers_cas():
    """AC27 : docs/pilotes/README.md enonce le process complet « issue -> cas
    d'eval » (verifications par tokens discriminants : aucun n'existe dans le
    README actuel, le test est rouge tant que la section n'est pas ecrite)."""
    texte = _read(PILOTES_README)
    bas = texte.casefold()
    assert "synthétique" in bas, "Annonce synthetique obligatoire non enoncee (AC27)"
    assert "versionn" in bas and "jamais" in bas, (
        "L'interdiction de versionner un extrait reel doit etre explicite (AC27)"
    )
    assert "cases/issue_" in texte, "Convention de nommage cases/issue_<n>.txt absente (AC27)"
    assert "test_eval_issue_" in texte, "Convention test_eval_issue_<n>.py absente (AC27)"
    assert re.search(r"(1|un)\s+(seul\s+)?appel", bas), (
        "Regle « 1 appel LLM par cas » absente (AC27)"
    )
    assert "xfail" in bas
    assert "strict=false" in bas and "strict=true" in bas, (
        "Politique xfail strict=False (LLM) / strict=True (deterministe) absente (AC27)"
    )
    assert "XFAIL" in texte, "Preuve de reproduction XFAIL avant merge absente (AC27)"
    assert "retir" in bas, "Checklist de retrait des xfail au chantier fix absente (AC27)"
    assert "flaky" in bas, "Traitement obligatoire du flaky absent (AC27)"
    assert "backend/evals/" in texte and "livr" in bas, (
        "L'item 1 de « Suites prevues » doit etre marque livre avec renvoi vers "
        "backend/evals/ (AC27)"
    )


def test_ac28_claude_md_et_context_md_mis_a_jour():
    """AC28 : backend/CLAUDE.md mentionne evals.yml et la separation des
    suites ; CONTEXT.md §0 mentionne le harnais et le prerequis cle CI dediee
    + usage limit."""
    claude = _read(BACKEND_CLAUDE)
    assert "evals.yml" in claude, "backend/CLAUDE.md ne mentionne pas evals.yml (AC28)"
    assert "evals/" in claude, "backend/CLAUDE.md ne mentionne pas backend/evals/ (AC28)"
    assert re.search(r"(payant|vrais appels)", claude.casefold()), (
        "La separation gratuite/payante (vrais appels) doit etre explicite (AC28)"
    )

    contexte = _read(CONTEXT_MD)
    debut = contexte.find("## 0.")
    assert debut != -1, "CONTEXT.md : section §0 introuvable"
    fin = contexte.find("\n## ", debut + 1)
    section0 = contexte[debut: fin if fin != -1 else len(contexte)]
    bas = section0.casefold()
    assert "harnais" in bas or "evals" in bas, (
        "CONTEXT.md §0 ne mentionne pas le harnais d'evaluation (AC28)"
    )
    assert "usage limit" in bas or "limite d'usage" in bas, (
        "CONTEXT.md §0 ne mentionne pas le prerequis usage limit (AC28)"
    )
    assert "openai" in bas or "clé ci" in bas or "cle ci" in bas, (
        "CONTEXT.md §0 ne mentionne pas la cle CI dediee (AC28)"
    )
