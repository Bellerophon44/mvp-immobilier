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

export interface ApiResult {
  global_score: number;
  verdict: string;
  confidence: string;
  pillars: ApiPillar[];
  actions: {
    check: string[];
    questions: string[];
    negotiation: string[];
  };
}

export async function analyzeListing(
  input: string,
  mode: "url" | "text",
  district?: string,
): Promise<ApiResult> {
  const trimmed = input.trim();
  const body: Record<string, string> =
    mode === "url" ? { url: trimmed } : { raw_text: trimmed };
  if (district) body.district = district;

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
