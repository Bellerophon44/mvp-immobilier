import logging

import app.llm_semantic as llm


def test_llm_fallback_logs_marker_and_returns_fallback(monkeypatch, caplog):
    # Verrou de regression pour le monitoring qualite IA (req 9.3, differe) : le
    # seul signal loggable d'une degradation LLM est le message "LLM call failed"
    # (logger llm_semantic, niveau ERROR). Tout monitoring futur s'appuiera dessus,
    # donc ce marqueur ne doit pas disparaitre ni changer silencieusement.
    def _boom(*args, **kwargs):
        raise RuntimeError("simulated OpenAI outage")

    monkeypatch.setattr(llm.client.chat.completions, "create", _boom)

    with caplog.at_level(logging.ERROR, logger="llm_semantic"):
        # Texte unique pour ne pas tomber sur une entree de cache.
        result = llm.analyze_semantic("annonce unique de regression monitoring 9.3")

    markers = [
        r for r in caplog.records
        if r.name == "llm_semantic"
        and r.levelno == logging.ERROR
        and "LLM call failed" in r.getMessage()
    ]
    assert markers, "le marqueur 'LLM call failed' (ERROR, logger llm_semantic) doit etre emis"

    # Depuis 9.10 (SPEC §3.4), le retour de fallback porte un marqueur interne
    # `_fallback: True` lu par `run_full_analysis` pour compter l'event serveur
    # `llm_fallback` (jamais expose dans AnalyzeResponse). Le contenu de fallback
    # (`_FALLBACK`) reste inchange ; on verifie l'egalite sur ce contenu, marqueur
    # interne mis a part, plutot qu'une identite stricte avec `_FALLBACK`.
    assert result["_fallback"] is True
    assert {k: v for k, v in result.items() if k != "_fallback"} == llm._FALLBACK
    assert result["summary"] == "Analyse indisponible."
    assert result["questions"] == []
