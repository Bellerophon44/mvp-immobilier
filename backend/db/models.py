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
