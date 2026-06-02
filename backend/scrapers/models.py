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

    def to_dict(self) -> dict:
        return asdict(self)
