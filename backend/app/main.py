import hmac
import logging
import os
import re
from typing import Any, Optional, Dict, List, Literal

from fastapi import FastAPI, HTTPException, Header, Body, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator

from app.analysis import run_full_analysis
from app.rate_limit import rate_limiter
from app.url_fetch import fetch_listing, extract_image_urls
from db.session import init_db, SessionLocal
from db.models import Comparable, Feedback, Event
from ingestion.save import (
    save_comparables,
    MIN_PRICE_M2,
    MAX_PRICE_M2,
    OUT_OF_SCOPE_CITIES,
    IN_SCOPE_DEPARTMENT,
)
from scrapers.base import canonical_city, canonical_district


logging.basicConfig(level=logging.INFO, force=True)
logger = logging.getLogger("mvp")
feedback_logger = logging.getLogger("feedback")
# Logger sans dimension sensible : au plus le `name` et des booleens de presence,
# jamais une valeur de dimension (referrer_domain, path), jamais une IP.
events_logger = logging.getLogger("events")


app = FastAPI(
    title="MVP Analyse Immobilière",
    description="API d'analyse de cohérence d'une annonce immobilière",
    version="1.0",
)


# Origines autorisees par defaut : dev local + domaine custom prod/staging
# (coherence-metz.fr). La regex `*.vercel.app` ci-dessous couvre en plus les
# previews Vercel. `CORS_ORIGINS` (env Fly) peut surcharger cette liste par env.
_default_origins = ",".join([
    "http://localhost:3000",
    "https://coherence-metz.fr",
    "https://www.coherence-metz.fr",
    "https://staging.coherence-metz.fr",
])
_origins_env = os.getenv("CORS_ORIGINS", _default_origins)
_origins = [o.strip() for o in _origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    init_db()


class AnalyzeRequest(BaseModel):
    raw_text: Optional[str] = None
    url: Optional[str] = None
    # Quartier choisi par l'utilisateur (sélecteur front) pour affiner une
    # analyse restée au niveau ville. Optionnel ; prime sur l'extraction.
    district: Optional[str] = None
    # Adresse saisie par l'utilisateur (alternative manuelle au géocodage de la
    # couche C) : affine le feedback local (quartier déduit, adresse affichée).
    address: Optional[str] = None


class AnalyzeResponse(BaseModel):
    global_score: int
    verdict: str
    confidence: str
    pillars: list
    actions: Dict[str, list]
    # Bloc "Contexte local" non-scoré (couche A "Ancrage local"). None si le
    # quartier n'est pas reconnu.
    local_context: Optional[Dict[str, Any]] = None


class FeedbackIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = Field(default=None, max_length=1000)
    analysis_id: Optional[str] = None
    global_score: Optional[int] = None
    verdict: Optional[str] = None
    prompt_variant: Optional[str] = None


class EventIn(BaseModel):
    # Schema ferme (garde-fou anti-PII central) : `extra="forbid"` rejette tout
    # champ non declare (url, address, comment, props, raw_text, ip...) -> 422.
    # Chaque dimension est une enum fermee ou un booleen strict ; aucune surface
    # texte libre n'est acceptee. `referrer_domain` est borne au hostname.
    model_config = ConfigDict(extra="forbid")

    name: Literal[
        "page_view",
        "methode_view",
        "analysis_started",
        "analysis_succeeded",
        "analysis_failed",
        "report_export",
        "district_refine",
        "address_entered",
        "llm_fallback",
    ]
    mode: Optional[Literal["url", "text"]] = None
    score_band: Optional[Literal["lt40", "40_59", "60_79", "80plus"]] = None
    confidence: Optional[Literal["Élevée", "Moyenne", "Faible"]] = None
    pillar_price_status: Optional[
        Literal["aligne", "sous", "leger_sur", "fort_sur", "indetermine"]
    ] = None
    reason: Optional[Literal["url_unreachable", "no_input", "llm_fallback"]] = None
    format: Optional[Literal["copy", "pdf"]] = None
    from_scope: Optional[
        Literal["quartier", "secteur", "ville", "metropole", "indetermine"]
    ] = None
    to_scope: Optional[
        Literal["quartier", "secteur", "ville", "metropole", "indetermine"]
    ] = None
    address_entered: Optional[StrictBool] = None
    path: Optional[Literal["/", "/methode"]] = None
    # Hostname seul : un domaine ne contient ni `/` ni `?` (garde-fou serveur,
    # le tronquage est fait cote front via URL(...).hostname).
    referrer_domain: Optional[str] = Field(default=None, max_length=253)

    @field_validator("referrer_domain")
    @classmethod
    def _hostname_only(cls, v: Optional[str]) -> Optional[str]:
        # Whitelist positive : un hostname ne contient que [a-z0-9.-] (le front
        # envoie URL(...).hostname). Rejette ainsi path/query mais aussi userinfo
        # (user:pass@), fragment (#), port (:) et saut de ligne (anti
        # log-injection / fuite de credential dans une ligne anonyme).
        if v is not None and not re.fullmatch(r"[A-Za-z0-9.-]+", v):
            raise ValueError("referrer_domain doit etre un hostname seul ([a-z0-9.-])")
        return v


# ---------------------------------------------------------------------------
# Import administratif des comparables (protégé par token)
# ---------------------------------------------------------------------------

MAX_IMPORT_ITEMS = 10000


class ComparableIn(BaseModel):
    id: str
    source: str
    city: str
    property_type: str
    surface_m2: float
    price_total: float
    district: Optional[str] = None
    postal_code: Optional[str] = None
    dpe: Optional[str] = None
    construction_year: Optional[int] = None
    floor: Optional[int] = None
    has_elevator: Optional[bool] = None
    has_terrace: Optional[bool] = None
    has_balcony: Optional[bool] = None
    is_condo: Optional[bool] = None
    condo_fees: Optional[float] = None
    has_cellar: Optional[bool] = None
    parking: Optional[int] = None
    bedrooms: Optional[int] = None


class ImportRequest(BaseModel):
    items: List[ComparableIn]


def _check_admin_token(provided: Optional[str]) -> None:
    expected = os.getenv("ADMIN_TOKEN")
    if not expected:
        raise HTTPException(status_code=503, detail="Import désactivé (ADMIN_TOKEN non configuré).")
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="Token administrateur invalide.")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/")
def root() -> dict:
    return {"service": "mvp-immobilier", "docs": "/docs"}


@app.get("/admin/comparables/stats")
def comparables_stats(x_admin_token: Optional[str] = Header(default=None)) -> dict:
    _check_admin_token(x_admin_token)
    db = SessionLocal()
    try:
        total = db.query(Comparable).count()
        cities = (
            db.query(Comparable.city)
            .distinct()
            .limit(50)
            .all()
        )
    finally:
        db.close()
    return {"total": total, "cities": sorted(c[0] for c in cities)}


@app.post("/admin/comparables")
def import_comparables(
    payload: ImportRequest,
    x_admin_token: Optional[str] = Header(default=None),
) -> dict:
    _check_admin_token(x_admin_token)

    if len(payload.items) > MAX_IMPORT_ITEMS:
        raise HTTPException(
            status_code=413,
            detail=f"Trop d'éléments (max {MAX_IMPORT_ITEMS}).",
        )

    listings = [item.model_dump() for item in payload.items]
    saved = save_comparables(listings)

    db = SessionLocal()
    try:
        total = db.query(Comparable).count()
    finally:
        db.close()

    logger.info("ADMIN import: received=%d saved=%d total_in_db=%d",
                len(listings), saved, total)
    return {"received": len(listings), "saved": saved, "total_in_db": total}


class MaintenanceRequest(BaseModel):
    # Sécurité : par défaut on ne fait que SIMULER. Passer dry_run=false pour
    # appliquer réellement les suppressions / renommages.
    dry_run: bool = True
    extra_out_of_scope: List[str] = []


@app.post("/admin/comparables/maintenance")
def comparables_maintenance(
    payload: MaintenanceRequest = Body(default=MaintenanceRequest()),
    x_admin_token: Optional[str] = Header(default=None),
) -> dict:
    """
    Assainit l'historique : purge les comparables hors bande prix/m², purge les
    communes hors périmètre, et ré-applique la forme canonique aux villes.

    dry_run=true (défaut) ne fait que compter ce qui serait modifié.
    """
    _check_admin_token(x_admin_token)

    out_of_scope = OUT_OF_SCOPE_CITIES | {
        canonical_city(c) for c in payload.extra_out_of_scope
    }

    db = SessionLocal()
    purged_band = purged_zone = purged_dept = renamed = renamed_district = 0
    try:
        for c in db.query(Comparable).all():
            if c.price_m2 is None or c.price_m2 < MIN_PRICE_M2 or c.price_m2 > MAX_PRICE_M2:
                purged_band += 1
                if not payload.dry_run:
                    db.delete(c)
                continue

            canon = canonical_city(c.city)
            if canon in out_of_scope:
                purged_zone += 1
                if not payload.dry_run:
                    db.delete(c)
                continue

            # Code postal connu hors Moselle : purge fiable (les lignes sans
            # code postal restent couvertes par la blocklist de noms ci-dessus).
            if c.postal_code and not c.postal_code.startswith(IN_SCOPE_DEPARTMENT):
                purged_dept += 1
                if not payload.dry_run:
                    db.delete(c)
                continue

            if canon != c.city:
                renamed += 1
                if not payload.dry_run:
                    c.city = canon

            canon_d = canonical_district(c.district, canon)
            if canon_d != c.district:
                renamed_district += 1
                if not payload.dry_run:
                    c.district = canon_d

        if not payload.dry_run:
            db.commit()
        total_after = db.query(Comparable).count()
    finally:
        db.close()

    result = {
        "dry_run": payload.dry_run,
        "purged_band": purged_band,
        "purged_zone": purged_zone,
        "purged_dept": purged_dept,
        "renamed": renamed,
        "renamed_district": renamed_district,
        "total_after": total_after,
    }
    logger.info("ADMIN maintenance: %s", result)
    return result


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(
    payload: AnalyzeRequest,
    _rl: None = Depends(rate_limiter(limit=10, window_seconds=60)),
):
    raw_text_preview = (payload.raw_text or "")[:60]
    logger.info(
        "ANALYZE in: has_raw_text=%s (len=%d, preview=%r), has_url=%s (%r)",
        bool(payload.raw_text and payload.raw_text.strip()),
        len(payload.raw_text or ""),
        raw_text_preview,
        bool(payload.url),
        payload.url,
    )

    if not payload.raw_text and not payload.url:
        raise HTTPException(
            status_code=400,
            detail="Veuillez fournir soit le texte de l'annonce, soit une URL.",
        )

    image_urls = None
    if payload.raw_text and payload.raw_text.strip():
        logger.info("ANALYZE branch: using raw_text")
        raw_content = payload.raw_text
    else:
        logger.info("ANALYZE branch: fetching URL")
        url = payload.url or ""
        fetched = fetch_listing(url)
        if not fetched or not fetched.get("text"):
            raise HTTPException(
                status_code=422,
                detail=(
                    "Impossible de récupérer le contenu de cette URL. "
                    "Le site bloque peut-être l'accès automatique. "
                    "Copiez-collez directement le texte de l'annonce."
                ),
            )
        raw_content = fetched["text"]
        # Les URLs d'images servent uniquement au screening photo en transit ;
        # elles ne sont jamais incluses dans la reponse /analyze (anti-pattern #3).
        image_urls = extract_image_urls(fetched.get("html") or "", url) or None

    try:
        return run_full_analysis(
            raw_content,
            district_override=payload.district or "",
            address=payload.address or "",
            image_urls=image_urls,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de l'analyse : {str(e)}",
        )


@app.post("/feedback", status_code=201)
def submit_feedback(
    payload: FeedbackIn,
    _rl: None = Depends(rate_limiter(limit=60, window_seconds=60)),
) -> dict:
    db = SessionLocal()
    try:
        row = Feedback(
            rating=payload.rating,
            comment=payload.comment,
            analysis_id=payload.analysis_id,
            global_score=payload.global_score,
            verdict=payload.verdict,
            prompt_variant=payload.prompt_variant,
        )
        db.add(row)
        db.commit()
    finally:
        db.close()

    # Le contenu du commentaire n'est jamais journalise (donnees perso possibles).
    feedback_logger.info(
        "FEEDBACK in: rating=%d has_comment=%s analysis_id=%s",
        payload.rating,
        bool(payload.comment),
        payload.analysis_id,
    )
    return {"status": "ok"}


@app.post("/events", status_code=201)
def submit_event(
    payload: EventIn,
    _rl: None = Depends(rate_limiter(limit=120, window_seconds=60)),
) -> dict:
    # Proxy de tendance best-effort (anonyme, agrege) : on persiste les seules
    # dimensions fermees validees par EventIn, aucune surface texte libre.
    db = SessionLocal()
    try:
        row = Event(
            name=payload.name,
            mode=payload.mode,
            score_band=payload.score_band,
            confidence=payload.confidence,
            pillar_price_status=payload.pillar_price_status,
            reason=payload.reason,
            format=payload.format,
            from_scope=payload.from_scope,
            to_scope=payload.to_scope,
            address_entered=payload.address_entered,
            path=payload.path,
            referrer_domain=payload.referrer_domain,
        )
        db.add(row)
        db.commit()
    finally:
        db.close()

    # Au plus le `name` et des booleens de presence : jamais une valeur de
    # dimension potentiellement sensible (referrer_domain, path), jamais d'IP.
    events_logger.info(
        "EVENT in: name=%s has_referrer=%s",
        payload.name,
        bool(payload.referrer_domain),
    )
    return {"status": "ok"}
