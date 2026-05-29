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

    def to_dict(self) -> dict:
        return asdict(self)
