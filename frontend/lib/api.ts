export interface ApiPillar {
  label: string;
  verdict: string;
  explanation: string;
  // Part du pilier dans le score global (prix /40, transparence /30, risque /30) :
  // global = somme des `points`. Affiché tel quel, sans recalcul côté front.
  points?: number;
  max?: number;
  // Périmètre structuré du pilier prix (les autres piliers ne les renseignent pas).
  scope?: "quartier" | "secteur" | "metropole" | "ville" | null;
  scope_name?: string | null;
  dpe_band?: string | null;
  n_comparables?: number | null;
  refinable?: boolean;
}

// Allégation locale de l'annonce confrontée au profil de quartier (couche B).
export interface LocalClaim {
  text: string;
  type: string;
  status: "coherent" | "a_verifier" | "peu_plausible";
  note: string;
  // Screening photo des allégations visuellement vérifiables (mode URL). Optionnel
  // -> rétro-compatible avec les anciennes réponses sans bloc photo.
  photo_status?: "confirme" | "non_trouve" | "non_applicable";
}

// Fait du Contexte local (distance / temps de trajet vers un POI ou une école).
// `label`/`value` sont toujours présents (rétro-compatible). Les champs de
// routing (couche C) sont optionnels : absents en repli Haversine.
export interface LocalFact {
  label: string;
  value: string;
  // Mode de trajet réel quand un temps routé est disponible (volet C). Absent en
  // repli Haversine : l'absence de `mode` (ou `estimated=true`) signifie distance
  // à vol d'oiseau.
  mode?: "WALK" | "DRIVE" | "BICYCLE" | "TRANSIT";
  duration_s?: number;
  distance_m?: number;
  // true => `value` est une distance Haversine ("à vol d'oiseau"), pas un temps réel.
  estimated?: boolean;
  // Identifiant de POI permettant de redemander un autre mode via POST /travel-times.
  // Présent sur les facts de POI routables (cathedrale/gare/pompidou/a31), absent
  // sur les facts écoles (non routables au lot 1).
  poi_id?: string;
}

// Bloc "Contexte local" non-scoré (couches A + B "Ancrage local"). Absent / null
// si le quartier n'est pas reconnu côté backend.
export interface LocalContext {
  district: string;
  summary: string;
  facts: LocalFact[];
  claims?: LocalClaim[];
  address?: string;
  // "adresse" = distances exactes (géocodage, couche C) ; "quartier" = repli sur
  // le profil de quartier (distances approximatives).
  precision?: "quartier" | "adresse";
  // Réserve C2 : présent quand le quartier vient d'un choix utilisateur que
  // l'annonce ne confirme pas. Optionnel -> rétro-compatible avec les anciennes
  // réponses.
  district_caveat?: string;
}

export interface ApiResult {
  global_score: number;
  verdict: string;
  confidence: string;
  pillars: ApiPillar[];
  actions: {
    questions: string[];
    negotiation: string[];
  };
  local_context?: LocalContext | null;
}

export async function analyzeListing(
  input: string,
  mode: "url" | "text",
  district?: string,
  address?: string,
): Promise<ApiResult> {
  const trimmed = input.trim();
  const body: Record<string, string> =
    mode === "url" ? { url: trimmed } : { raw_text: trimmed };
  if (district) body.district = district;
  if (address && address.trim()) body.address = address.trim();

  const response = await fetch(
    process.env.NEXT_PUBLIC_API_URL + "/analyze",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }
  );

  if (!response.ok) {
    let detail = "Erreur lors de l'analyse.";
    try {
      const payload = await response.json();
      if (payload?.detail) detail = payload.detail;
    } catch {
      // ignore parse error
    }
    throw new Error(detail);
  }

  return response.json();
}

// Temps de trajet à la demande (volet C, endpoint POST /travel-times). On ré-envoie
// l'adresse texte (déjà côté client) ; aucune coordonnée ne circule (RGPD).
export interface TravelTimesRequest {
  address: string;
  mode: "WALK" | "DRIVE" | "BICYCLE" | "TRANSIT";
  city_hint?: string;
}

export interface TravelTimeResult {
  poi_id: string;
  label: string;
  value: string;
  label_mode?: string; // "à pied" | "en voiture" | "à vélo" | "en transports"
  duration_s?: number;
  distance_m?: number;
  estimated?: boolean; // true => repli vol d'oiseau
  mode?: string; // "vol_oiseau" en repli
}

export interface TravelTimesResponse {
  status: "ok" | "indisponible";
  mode?: string;
  reason?: "adresse" | "routing";
  results?: TravelTimeResult[];
}

// Recalcule les temps de trajet pour un mode donné. Best-effort côté UI : en cas
// d'erreur réseau on renvoie un statut indisponible plutôt que de jeter.
export async function fetchTravelTimes(
  address: string,
  mode: TravelTimesRequest["mode"],
  cityHint?: string,
): Promise<TravelTimesResponse> {
  const body: TravelTimesRequest = { address, mode };
  if (cityHint) body.city_hint = cityHint;
  try {
    const response = await fetch(
      process.env.NEXT_PUBLIC_API_URL + "/travel-times",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      },
    );
    if (!response.ok) {
      return { status: "indisponible", reason: "routing" };
    }
    return response.json();
  } catch {
    return { status: "indisponible", reason: "routing" };
  }
}

export interface FeedbackPayload {
  rating: number;
  comment?: string;
  analysis_id?: string;
  global_score?: number;
  verdict?: string;
}

// Envoi non bloquant : un echec de feedback ne doit jamais degrader l'UX.
export async function sendFeedback(payload: FeedbackPayload): Promise<boolean> {
  try {
    const response = await fetch(
      process.env.NEXT_PUBLIC_API_URL + "/feedback",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }
    );
    return response.ok;
  } catch {
    return false;
  }
}

// Event produit anonyme (instrumentation funnel, 9.10). Proxy de tendance
// best-effort : fire-and-forget calque sur sendFeedback. Jamais awaite dans un
// chemin critique, jamais d'exception remontee — un echec d'event ne doit ni
// retarder ni alterer le flux d'analyse. Aucune PII : seules des dimensions
// fermees (enums/bands/booleens) validees serveur cote /events.
export function sendEvent(name: string, props?: Record<string, unknown>): void {
  try {
    void fetch(process.env.NEXT_PUBLIC_API_URL + "/events", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, ...(props || {}) }),
      keepalive: true,
    }).catch(() => {});
  } catch {
    // Avale toute erreur synchrone (URL absente, etc.) : best-effort.
  }
}
