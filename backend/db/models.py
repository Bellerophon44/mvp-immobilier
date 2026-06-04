from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class Comparable(Base):
    """
    Représente une annonce immobilière comparable,
    utilisée uniquement à des fins statistiques.
    """

    __tablename__ = "comparables"

    # Identifiant interne stable (hash source + id annonce)
    id = Column(String, primary_key=True, index=True)

    # Source de l’annonce (ex: agence locale, portail)
    source = Column(String, nullable=False)

    # Localisation
    city = Column(String, nullable=False)
    district = Column(String, nullable=True)
    postal_code = Column(String, nullable=True)  # code postal 5 chiffres (filtre dépt)

    # Typologie du bien
    property_type = Column(String, nullable=False)

    # Données numériques
    surface_m2 = Column(Float, nullable=False)
    price_total = Column(Float, nullable=False)
    price_m2 = Column(Float, nullable=False)

    # Critères affinés (chantier B) — nullable, taux de remplissage variable
    dpe = Column(String, nullable=True)               # lettre A-G
    construction_year = Column(Integer, nullable=True)

    # Critères affinés (chantier C) — nullable, taux de remplissage variable
    floor = Column(Integer, nullable=True)            # étage
    has_elevator = Column(Boolean, nullable=True)     # ascenseur
    has_terrace = Column(Boolean, nullable=True)      # terrasse
    has_balcony = Column(Boolean, nullable=True)      # balcon
    is_condo = Column(Boolean, nullable=True)         # en copropriété
    condo_fees = Column(Float, nullable=True)         # charges annuelles copro (€)
    has_cellar = Column(Boolean, nullable=True)       # cave
    parking = Column(Integer, nullable=True)          # nombre de places de parking
    bedrooms = Column(Integer, nullable=True)         # nombre de chambres

    # Date de collecte
    collected_at = Column(DateTime, default=datetime.utcnow)


class Feedback(Base):
    """
    Retour utilisateur post-analyse, a finalite interne (amelioration prompt LLM
    et wording UX). Minimisation RGPD : ni IP, ni identifiant, ni extrait d'annonce.
    """

    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rating = Column(Integer, nullable=False)
    comment = Column(String, nullable=True)
    analysis_id = Column(String, nullable=True)
    global_score = Column(Integer, nullable=True)
    verdict = Column(String, nullable=True)
    # Pre-cablage 9.8 (A/B prompts), aucune logique en 9.7.
    prompt_variant = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
