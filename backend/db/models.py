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

    # Tracking temporel (chantier cross-agence, increment 1) — nullable pour ne
    # pas casser les lignes prod existantes ; poses applicativement par
    # ingestion/save.py. first_seen_at n'est JAMAIS reecrit ; last_seen_at est
    # rafraichi a chaque passage de collecte.
    first_seen_at = Column(DateTime, nullable=True)
    last_seen_at = Column(DateTime, nullable=True)

    # Re-link "sans photo" meme agence (chantier cross-agence, increment 2a) —
    # identifiants techniques INTERNES (jamais exposes en reponse API). reference
    # = reference de mandat (bienici cle JSON ; HTML agences best-effort) ;
    # customer_id = compte annonceur bienici. lineage_id = lignee du bien physique
    # (survit au changement d'id), posee applicativement par ingestion/save.py
    # (repli `lineage_id or id` en lecture pour les lignes heritees).
    reference = Column(String, nullable=True)
    customer_id = Column(String, nullable=True)
    lineage_id = Column(String, nullable=True, index=True)

    # URLs photo captees a la collecte (bienici cle JSON `photos`, increment 2b
    # etape 1) — liste d'URLs encodee JSON (json.dumps) ou None. Metadonnee
    # technique INTERNE (usage futur : hash perceptuel etape 2), JAMAIS exposee
    # en reponse API. Pas d'index (jamais un critere de filtre).
    photo_urls = Column(String, nullable=True)


class ListingPriceSnapshot(Base):
    """
    Snapshot de prix d'une annonce (chantier cross-agence, increment 1) : une
    ligne a la premiere observation puis une par changement de price_total
    (mode delta, anti-gonflement). Pas de FK formelle vers comparables
    (SQLite/MVP) : coherence applicative, la purge de retention supprime
    explicitement les snapshots des ids purges.
    """

    __tablename__ = "listing_price_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    listing_id = Column(String, nullable=False, index=True)
    price_total = Column(Float, nullable=False)
    price_m2 = Column(Float, nullable=False)
    observed_at = Column(DateTime, nullable=False)


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


class Event(Base):
    """
    Event produit first-party, anonyme et agrege (entonnoir de conversion).
    Minimisation RGPD (esprit `Feedback`) : ni IP, ni identifiant, ni extrait
    d'annonce, ni texte libre. Chaque dimension est une colonne typee fermee
    (enum/bool/band), validee a l'entree par `EventIn`. Les compteurs sont des
    proxys de tendance (best-effort), pas une comptabilite exacte.
    """

    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)

    # Dimensions, toutes nullable : une ligne ne porte que celles de son event.
    mode = Column(String, nullable=True)
    score_band = Column(String, nullable=True)
    confidence = Column(String, nullable=True)
    pillar_price_status = Column(String, nullable=True)
    reason = Column(String, nullable=True)
    format = Column(String, nullable=True)
    from_scope = Column(String, nullable=True)
    to_scope = Column(String, nullable=True)
    address_entered = Column(Boolean, nullable=True)
    path = Column(String, nullable=True)
    referrer_domain = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
