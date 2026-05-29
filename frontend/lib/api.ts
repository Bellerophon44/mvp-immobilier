export interface ApiPillar {
  label: string;
  verdict: string;
  explanation: string;
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

export async function analyzeListing(input: string, mode: "url" | "text"): Promise<ApiResult> {
  const trimmed = input.trim();
  const body = mode === "url" ? { url: trimmed } : { raw_text: trimmed };

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
