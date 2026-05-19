import os
from typing import Optional, Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.analysis import run_full_analysis
from db.session import init_db


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


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/")
def root() -> dict:
    return {"service": "mvp-immobilier", "docs": "/docs"}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(payload: AnalyzeRequest):
    if not payload.raw_text and not payload.url:
        raise HTTPException(
            status_code=400,
            detail="Veuillez fournir soit le texte de l'annonce, soit une URL.",
        )

    raw_content = payload.raw_text or payload.url

    try:
        return run_full_analysis(raw_content)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de l'analyse : {str(e)}",
        )
