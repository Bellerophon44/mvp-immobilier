"""Screening photo des allégations locales (Phase 0+1).

Pour les seules allégations locales visuellement vérifiables (types cathedrale /
nature / autre), un unique appel multimodal confirme ou non chaque allégation à
partir des photos de l'annonce. Bloc NON-scoré : n'entre jamais dans le score
40/30/30. Repli sûr sur `non_trouve` à la moindre incertitude ou erreur.
"""

import hashlib
import json
import logging
import time
from typing import Any, Dict, List

from app.llm_semantic import client, MODEL_NAME


logger = logging.getLogger("photo_evidence")
logger.setLevel(logging.INFO)


# Types d'allégations éligibles à la vérification photo (décision GATE 1).
ELIGIBLE_TYPES = {"cathedrale", "nature", "autre"}

# Statuts retournables ; `non_trouve` est le défaut sûr (jamais `confirme` par
# défaut ou par complaisance).
VALID_STATUSES = {"confirme", "non_trouve", "non_applicable"}

MAX_IMAGES = 6
TEMPERATURE = 0.2

_CACHE: Dict[str, Any] = {}
CACHE_TTL_SECONDS = 7 * 24 * 60 * 60


SYSTEM_PROMPT = (
    "Tu es un verificateur visuel honnete et strict d'annonces immobilieres "
    "messines. On te donne des allegations de localisation extraites d'une "
    "annonce et les photos de cette annonce. Pour chaque allegation, tu reponds "
    "par un statut : 'confirme' UNIQUEMENT si une image montre l'element SANS "
    "AMBIGUITE ; au moindre doute, 'non_trouve' ; 'non_applicable' si une "
    "allegation de type 'autre' n'est pas un repere visuel identifiable sur une "
    "photo. Tu ne confirmes jamais par complaisance. "
    "Reperes visuels messins a reconnaitre : la Cathedrale Saint-Etienne ; la "
    "Moselle et les plans d'eau (nature) ; le Centre Pompidou-Metz ; le Temple "
    "Neuf ; le Jardin Botanique ; ainsi que toute vue atypique remarquable. "
    "Tu n'estimes aucun prix. Tu reponds en JSON strict."
)


def _normalize_claim(claim: Dict[str, Any]) -> Dict[str, str]:
    return {
        "text": str(claim.get("text") or "").strip(),
        "type": str(claim.get("type") or "").strip(),
    }


def _eligible_claims(claims: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [c for c in claims if (c.get("type") in ELIGIBLE_TYPES)]


def _cache_key(image_urls: List[str], eligible: List[Dict[str, Any]]) -> str:
    payload = {
        "images": list(image_urls),
        "claims": [_normalize_claim(c) for c in eligible],
    }
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _get_from_cache(key: str):
    item = _CACHE.get(key)
    if not item:
        return None
    timestamp, value = item
    if time.time() - timestamp > CACHE_TTL_SECONDS:
        del _CACHE[key]
        return None
    return value


def _set_cache(key: str, value: Dict[int, str]) -> None:
    _CACHE[key] = (time.time(), value)


def _build_user_parts(eligible: List[Dict[str, Any]], images: List[str]) -> list:
    lines = [
        "Voici les allegations a verifier (index : texte) :",
    ]
    for idx, claim in enumerate(eligible):
        lines.append(f"{idx} : {_normalize_claim(claim)['text']}")
    lines.append(
        "Reponds UNIQUEMENT par un objet JSON de la forme "
        '{"results": {"0": "confirme|non_trouve|non_applicable", ...}} '
        "avec une cle par index d'allegation ci-dessus."
    )
    parts: list = [{"type": "text", "text": "\n".join(lines)}]
    for url in images:
        parts.append({"type": "image_url", "image_url": {"url": url, "detail": "low"}})
    return parts


def _parse_statuses(content: str, count: int) -> Dict[int, str]:
    """Mappe chaque index d'allegation eligible vers un statut valide. Tout
    statut hors enum, manquant ou JSON non parsable -> `non_trouve` (defaut sur)."""
    statuses = {i: "non_trouve" for i in range(count)}
    try:
        data = json.loads(content or "{}")
    except (ValueError, TypeError):
        return statuses
    results = data.get("results") if isinstance(data, dict) else None
    if not isinstance(results, dict):
        return statuses
    for i in range(count):
        raw = results.get(str(i), results.get(i))
        if isinstance(raw, str) and raw.strip() in VALID_STATUSES:
            statuses[i] = raw.strip()
    return statuses


def assess_claims_with_photos(
    claims: List[Dict[str, Any]], image_urls: List[str]
) -> Dict[int, str]:
    """Confronte les allegations locales eligibles aux photos de l'annonce.

    Retourne un mapping {index dans la liste `claims` d'origine -> photo_status}.
    Seuls les claims eligibles (type cathedrale/nature/autre) apparaissent. Aucun
    appel vision si 0 claim eligible ou aucune image. Repli silencieux sur
    `non_trouve` a la moindre erreur (jamais de raise propage).
    """
    image_urls = list(image_urls or [])
    eligible_idx = [
        i for i, c in enumerate(claims or []) if c.get("type") in ELIGIBLE_TYPES
    ]

    if not eligible_idx or not image_urls:
        return {}

    eligible = [claims[i] for i in eligible_idx]
    images = image_urls[:MAX_IMAGES]

    key = _cache_key(images, eligible)
    cached = _get_from_cache(key)
    if cached is not None:
        return dict(cached)

    statuses_by_pos: Dict[int, str]
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            temperature=TEMPERATURE,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_parts(eligible, images)},
            ],
        )
        content = response.choices[0].message.content or "{}"
        statuses_by_pos = _parse_statuses(content, len(eligible))
        logger.info(
            "photo vision call: claims=%d images=%d", len(eligible), len(images)
        )
    except Exception:
        logger.exception("photo vision call failed; falling back to non_trouve")
        statuses_by_pos = {i: "non_trouve" for i in range(len(eligible))}

    mapping = {eligible_idx[pos]: status for pos, status in statuses_by_pos.items()}
    _set_cache(key, mapping)
    return mapping
