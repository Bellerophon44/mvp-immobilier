function looksLikeUrl(input: string): boolean {
  const trimmed = input.trim();
  return /^https?:\/\//i.test(trimmed);
}

export async function analyzeListing(input: string) {
  const trimmed = input.trim();
  const body = looksLikeUrl(trimmed)
    ? { url: trimmed }
    : { raw_text: trimmed };

  const response = await fetch(
    process.env.NEXT_PUBLIC_API_URL + "/analyze",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    }
  );

  if (!response.ok) {
    let detail = "Erreur lors de l'analyse.";
    try {
      const payload = await response.json();
      if (payload?.detail) detail = payload.detail;
    } catch {
      // ignore parse error, keep default detail
    }
    throw new Error(detail);
  }

  return response.json();
}
