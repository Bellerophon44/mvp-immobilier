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

    def to_dict(self) -> dict:
        return asdict(self)
