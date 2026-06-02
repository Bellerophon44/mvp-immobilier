import hmac
import logging
import os
from typing import Optional, Dict, List

from fastapi import FastAPI, HTTPException, Header, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.analysis import run_full_analysis
from app.url_fetch import fetch_listing_text
from db.session import init_db, SessionLocal
from db.models import Comparable
from ingestion.save import (
    save_comparables,
    MIN_PRICE_M2,
    MAX_PRICE_M2,
    OUT_OF_SCOPE_CITIES,
)
from scrapers.base import canonical_city, canonical_district


logging.basicConfig(level=logging.INFO, force=True)
logger = logging.getLogger("mvp")


app = FastAPI(
    title="MVP Analyse Immobilière",
    description="API d'analyse de cohérence d'une annonce immobilière",
    version="1.0",
)


_default_origins = "http://localhost:3000,https://*.vercel.app"
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


class AnalyzeResponse(BaseModel):
    global_score: int
    verdict: str
    confidence: str
    pillars: list
    actions: Dict[str, list]


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
    purged_band = purged_zone = renamed = renamed_district = 0
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
        "renamed": renamed,
        "renamed_district": renamed_district,
        "total_after": total_after,
    }
    logger.info("ADMIN maintenance: %s", result)
    return result


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(payload: AnalyzeRequest):
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

    if payload.raw_text and payload.raw_text.strip():
        logger.info("ANALYZE branch: using raw_text")
        raw_content = payload.raw_text
    else:
        logger.info("ANALYZE branch: fetching URL")
        fetched = fetch_listing_text(payload.url or "")
        if not fetched:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Impossible de récupérer le contenu de cette URL. "
                    "Le site bloque peut-être l'accès automatique. "
                    "Copiez-collez directement le texte de l'annonce."
                ),
            )
        raw_content = fetched

    try:
        return run_full_analysis(raw_content)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de l'analyse : {str(e)}",
        )
