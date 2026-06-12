"""Oracle de separation des suites (spec evals-harness §7.1, AC3).

La suite gratuite (tests/) ne doit JAMAIS collecter backend/evals/ : les evals
exigent une vraie cle OpenAI et font de vrais appels payants ; collectes par
test.yml (cle factice), ils echoueraient en rouge parasite. L'isolation repose
sur backend/pytest.ini (`testpaths = tests`) — ces deux tests echouent si le
fichier disparait ou si testpaths est elargi.
"""

import configparser
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def test_session_ne_collecte_aucun_item_evals(request):
    """Oracle dynamique : aucun item de la session pytest courante n'a un
    chemin contenant le segment `evals`."""
    fuites = [
        item.nodeid
        for item in request.session.items
        if "evals" in item.nodeid.replace("\\", "/").split("::")[0].split("/")
    ]
    assert not fuites, (
        "La suite gratuite collecte des items evals/ (pytest.ini supprime ou "
        f"testpaths elargi ?) : {fuites}"
    )


def test_pytest_ini_declare_testpaths_tests():
    """Oracle statique : pytest.ini existe et declare exactement
    `testpaths = tests`."""
    ini = BACKEND / "pytest.ini"
    assert ini.is_file(), "backend/pytest.ini absent : l'isolation des evals saute"
    cfg = configparser.ConfigParser()
    cfg.read(ini, encoding="utf-8")
    assert cfg.has_section("pytest"), "section [pytest] absente de pytest.ini"
    assert cfg.get("pytest", "testpaths", fallback="").strip() == "tests", (
        "pytest.ini doit declarer exactement `testpaths = tests`"
    )
