"""Spike A — Les URLs d'images d'une annonce sont-elles fetchables par OpenAI ?

Tranche la cascade photo du portage mobile (cf.
`docs/specs/mobile-app-ANALYSE.md` §5) : quand l'app extrait le texte d'une
annonce sur l'appareil (mode `raw_text`, ex. LeBonCoin), faut-il

  - Option 1 : envoyer les URLs d'images et laisser les serveurs d'OpenAI les
    fetcher (comportement actuel de `app/photo_evidence.py`, peu coûteux) ; OU
  - Option 2 : téléverser les octets des images depuis l'appareil (plus lourd,
    glissement RGPD) parce que les URLs sont signées / verrouillées par Referer /
    expirantes et donc INFETCHABLES par un tiers comme OpenAI.

Ce script prend en entrée de VRAIES URLs d'images d'annonce (à récupérer depuis
un navigateur / téléphone : clic droit -> copier l'adresse de l'image, ou
DevTools) et mesure deux choses indépendantes :

  1. Fetch direct depuis cette machine, avec plusieurs profils d'en-têtes
     (bare / UA navigateur / UA + Referer). Indicatif du comportement d'un
     fetch datacenter.
  2. Fetch par OpenAI : un appel vision par URL ; on détecte si l'API échoue à
     télécharger l'image (-> INFETCHABLE) et, si elle réussit, si le CDN a servi
     une vraie photo ou une page de blocage / un placeholder.

Le test (2) est l'AUTORITÉ pour la décision : il dit exactement si les serveurs
d'OpenAI atteignent l'image. Le test (1) peut être faussé par la politique
réseau de l'hôte (un 403 peut venir d'un proxy d'egress, pas du CDN distant) ;
à lire avec cette réserve.

Aucune entrée réseau de prod n'est touchée. À lancer là où l'egress HTTPS est
ouvert ET `OPENAI_API_KEY` est présent (poste local, ou runner CI avec le
secret). Exemples :

    python -m tools.probe_lbc_images "https://img.leboncoin.fr/api/v1/..jpg" "https://.."
    python -m tools.probe_lbc_images --file urls.txt --json-out report.json
    python -m tools.probe_lbc_images --file urls.txt --no-openai   # test (1) seul
"""

import argparse
import json
import logging
import sys
import urllib.request
from typing import Any, Dict, List, Optional

logger = logging.getLogger("probe_lbc_images")
logging.basicConfig(level=logging.INFO, format="%(message)s")


BROWSER_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"
)
FETCH_TIMEOUT = 15

# Marqueurs d'une erreur de TÉLÉCHARGEMENT côté OpenAI (l'image n'a pas pu être
# atteinte) — par opposition à une autre erreur d'API. La casse exacte des
# messages OpenAI peut évoluer : on compare en minuscules sur des fragments.
OPENAI_DOWNLOAD_ERROR_MARKERS = (
    "error while downloading",
    "timeout while downloading",
    "invalid_image_url",
    "failed to download",
    "unable to download",
    "could not be downloaded",
)


def _read_urls(args: argparse.Namespace) -> List[str]:
    urls: List[str] = list(args.urls or [])
    if args.file:
        with open(args.file, "r", encoding="utf-8") as fh:
            urls.extend(line.strip() for line in fh)
    # dédup en préservant l'ordre, ignore vides et commentaires
    seen: set = set()
    out: List[str] = []
    for u in urls:
        if not u or u.startswith("#") or u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out


def _fetch_profile(url: str, headers: Dict[str, str]) -> Dict[str, Any]:
    """Un GET avec un jeu d'en-têtes donné. Ne lève jamais : renvoie un dict de
    diagnostic (status, content_type, bytes, ok) ou une erreur capturée."""
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
            body = resp.read()
            ctype = resp.headers.get("Content-Type", "")
            return {
                "status": resp.status,
                "content_type": ctype,
                "bytes": len(body),
                "ok": resp.status == 200 and ctype.startswith("image/"),
            }
    except urllib.error.HTTPError as e:
        return {"status": e.code, "content_type": "", "bytes": 0, "ok": False,
                "error": f"HTTP {e.code}"}
    except Exception as e:  # noqa: BLE001 — diagnostic, on capture tout
        return {"status": None, "content_type": "", "bytes": 0, "ok": False,
                "error": f"{type(e).__name__}: {e}"}


def direct_fetch_report(url: str) -> Dict[str, Any]:
    """Teste 3 profils d'en-têtes : bare, UA navigateur, UA + Referer."""
    profiles = {
        "bare": {},
        "browser_ua": {"User-Agent": BROWSER_UA},
        "ua_referer": {"User-Agent": BROWSER_UA, "Referer": "https://www.leboncoin.fr/"},
    }
    return {name: _fetch_profile(url, hdrs) for name, hdrs in profiles.items()}


def openai_fetch_report(
    client: Any, model: str, detail: str, url: str
) -> Dict[str, Any]:
    """Un appel vision sur une URL. Distingue trois issues :
    - unfetchable : OpenAI n'a pas pu télécharger l'image (erreur d'API ciblée) ;
    - served_photo : OpenAI a reçu une vraie photo d'annonce ;
    - served_block : OpenAI a reçu une page de blocage / un placeholder (200 mais
      pas une photo) ;
    - api_error : autre erreur (clé, quota, modèle...).
    """
    prompt = (
        "Tu reçois UNE image provenant d'une URL d'annonce immobilière. "
        "Réponds en JSON strict : "
        '{"kind": "property_photo" | "block_or_placeholder" | "other", '
        '"desc": "<=8 mots"}. '
        "property_photo = vraie photo (intérieur, façade, vue, plan). "
        "block_or_placeholder = page d'erreur, captcha, logo, image grise/vide."
    )
    try:
        response = client.chat.completions.create(
            model=model,
            temperature=0.0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url",
                         "image_url": {"url": url, "detail": detail}},
                    ],
                }
            ],
        )
        content = response.choices[0].message.content or "{}"
        try:
            data = json.loads(content)
        except (ValueError, TypeError):
            data = {}
        kind = data.get("kind")
        outcome = "served_photo" if kind == "property_photo" else "served_block"
        return {"outcome": outcome, "kind": kind, "desc": data.get("desc")}
    except Exception as e:  # noqa: BLE001 — on classe l'erreur
        msg = str(e).lower()
        if any(m in msg for m in OPENAI_DOWNLOAD_ERROR_MARKERS):
            return {"outcome": "unfetchable", "error": str(e)}
        return {"outcome": "api_error", "error": str(e)}


def _make_openai_client() -> Any:
    import os
    from openai import OpenAI

    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise SystemExit(
            "OPENAI_API_KEY absent. Lancer avec la clé, ou --no-openai pour le "
            "seul test de fetch direct."
        )
    return OpenAI(api_key=key)


def main() -> int:
    import os

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("urls", nargs="*", help="URLs d'images d'annonce")
    parser.add_argument("--file", help="Fichier d'URLs (une par ligne, # = commentaire)")
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))
    parser.add_argument("--detail", default="high", choices=["high", "low", "auto"])
    parser.add_argument("--no-openai", action="store_true",
                        help="Saute le test OpenAI (fetch direct seulement)")
    parser.add_argument("--json-out", help="Écrit le rapport complet en JSON")
    args = parser.parse_args()

    urls = _read_urls(args)
    if not urls:
        parser.error("Aucune URL fournie (positionnelles ou --file).")

    client = None if args.no_openai else _make_openai_client()
    results: List[Dict[str, Any]] = []

    for i, url in enumerate(urls, 1):
        logger.info("\n[%d/%d] %s", i, len(urls), url)
        direct = direct_fetch_report(url)
        for name, r in direct.items():
            logger.info("  direct/%-11s status=%s ct=%s bytes=%s ok=%s%s",
                        name, r.get("status"), r.get("content_type") or "-",
                        r.get("bytes"), r.get("ok"),
                        f"  {r['error']}" if r.get("error") else "")
        entry: Dict[str, Any] = {"url": url, "direct": direct}

        if client is not None:
            oai = openai_fetch_report(client, args.model, args.detail, url)
            logger.info("  openai          outcome=%s%s%s",
                        oai.get("outcome"),
                        f" kind={oai['kind']}" if oai.get("kind") else "",
                        f" desc='{oai['desc']}'" if oai.get("desc") else "")
            if oai.get("error"):
                logger.info("    err: %s", oai["error"])
            entry["openai"] = oai
        results.append(entry)

    _summarize(results, used_openai=client is not None)

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(results, fh, ensure_ascii=False, indent=2)
        logger.info("\nRapport JSON: %s", args.json_out)
    return 0


def _summarize(results: List[Dict[str, Any]], used_openai: bool) -> None:
    n = len(results)
    direct_ok = sum(
        1 for r in results if any(p.get("ok") for p in r["direct"].values())
    )
    logger.info("\n========== SYNTHÈSE (%d URLs) ==========", n)
    logger.info("Fetch direct réussi (au moins un profil) : %d/%d "
                "(indicatif — peut être faussé par la politique réseau de l'hôte)",
                direct_ok, n)

    if not used_openai:
        logger.info("Test OpenAI sauté (--no-openai). La décision option 1/2 "
                    "exige le test OpenAI.")
        return

    photo = sum(1 for r in results if r.get("openai", {}).get("outcome") == "served_photo")
    block = sum(1 for r in results if r.get("openai", {}).get("outcome") == "served_block")
    unfetch = sum(1 for r in results if r.get("openai", {}).get("outcome") == "unfetchable")
    apierr = sum(1 for r in results if r.get("openai", {}).get("outcome") == "api_error")
    logger.info("OpenAI a vu une VRAIE photo        : %d/%d", photo, n)
    logger.info("OpenAI a reçu blocage/placeholder  : %d/%d", block, n)
    logger.info("OpenAI N'A PAS PU télécharger       : %d/%d", unfetch, n)
    if apierr:
        logger.info("Erreurs d'API (clé/quota/modèle)   : %d/%d "
                    "-> non concluant, à relancer", apierr, n)

    conclusive = photo + block + unfetch
    logger.info("\n---------- VERDICT ----------")
    if conclusive == 0:
        logger.info("NON CONCLUANT : aucune issue exploitable (erreurs d'API). "
                    "Vérifier la clé / le quota et relancer.")
        return
    if unfetch == 0 and block == 0:
        logger.info("OPTION 1 VIABLE : OpenAI fetche les URLs et voit de vraies "
                    "photos. Envoyer `image_urls` suffit (peu coûteux, RGPD "
                    "inchangé).")
    elif photo >= conclusive * 0.6 and unfetch == 0:
        logger.info("OPTION 1 PROBABLE mais à surveiller : %d/%d servies en "
                    "blocage/placeholder. Vérifier le lazy-load / les vraies URLs "
                    "de galerie avant de conclure.", block, conclusive)
    else:
        logger.info("OPTION 2 REQUISE : %d infetchables + %d blocages sur %d. "
                    "Prévoir l'upload d'octets depuis l'appareil (acter le "
                    "glissement RGPD).", unfetch, block, conclusive)


if __name__ == "__main__":
    sys.exit(main())
