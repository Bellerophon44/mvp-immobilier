export interface ApiPillar {
  label: string;
  verdict: string;
  explanation: string;
  // Périmètre structuré du pilier prix (les autres piliers ne les renseignent pas).
  scope?: "quartier" | "secteur" | "ville" | null;
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
}

// Bloc "Contexte local" non-scoré (couches A + B "Ancrage local"). Absent / null
// si le quartier n'est pas reconnu côté backend.
export interface LocalContext {
  district: string;
  summary: string;
  facts: { label: string; value: string }[];
  claims?: LocalClaim[];
  address?: string;
  // "adresse" = distances exactes (géocodage, couche C) ; "quartier" = repli sur
  // le profil de quartier (distances approximatives).
  precision?: "quartier" | "adresse";
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
