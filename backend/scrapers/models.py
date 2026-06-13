from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class PropertyListing:
    id: str
    source: str
    city: str
    property_type: str  # "appartement" | "maison"
    surface_m2: float
    price_total: float
    district: Optional[str] = None
    postal_code: Optional[str] = None      # code postal 5 chiffres, sinon None
    dpe: Optional[str] = None              # lettre A-G, sinon None
    construction_year: Optional[int] = None
    # Critères affinés (chantier C) — nullable, remplissage variable selon source.
    floor: Optional[int] = None            # étage
    has_elevator: Optional[bool] = None    # ascenseur
    has_terrace: Optional[bool] = None     # terrasse
    has_balcony: Optional[bool] = None     # balcon
    is_condo: Optional[bool] = None        # en copropriété
    condo_fees: Optional[float] = None     # charges annuelles de copropriété (€)
    has_cellar: Optional[bool] = None      # cave
    parking: Optional[int] = None          # nombre de places de parking
    bedrooms: Optional[int] = None         # nombre de chambres
    # Re-link "sans photo" meme agence (increment 2a) — identifiants techniques
    # INTERNES, nullable (best-effort selon la source). reference = mandat
    # (bienici + HTML agences best-effort) ; customer_id = compte annonceur
    # bienici (None hors bienici).
    reference: Optional[str] = None
    customer_id: Optional[str] = None
    # URLs photo captees a la collecte (increment 2b etape 1) — liste d'URLs
    # encodee JSON (str) ou None, homogene a la colonne String. Metadonnee
    # technique INTERNE (usage futur : hash etape 2), jamais exposee en API.
    photo_urls: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)
