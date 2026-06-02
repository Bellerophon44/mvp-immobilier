from sqlalchemy import Column, String, Float, Integer, DateTime
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

    # Date de collecte
    collected_at = Column(DateTime, default=datetime.utcnow)
