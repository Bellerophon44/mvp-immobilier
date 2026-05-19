export async function analyzeListing(rawText: string) {
  const response = await fetch(
    process.env.NEXT_PUBLIC_API_URL + "/analyze",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ raw_text: rawText })
    }
  );

  if (!response.ok) {
    throw new Error("Erreur API");
  }

  return response.json();
}
