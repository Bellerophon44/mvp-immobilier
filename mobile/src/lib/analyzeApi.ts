import { buildAnalyzeBody } from './analyzeBody';
import { getApiUrl } from './config';
import { ApiResult } from './types';

/**
 * Appelle POST {getApiUrl()}/analyze en mode raw_text (SPEC AC10/AC11) :
 *  - corps = buildAnalyzeBody(rawText, imageUrls) (raw_text + image_urls, jamais url) ;
 *  - en-tete Content-Type: application/json, methode POST ;
 *  - reponse non-ok => rejet avec le detail backend (pas de faux succes) ;
 *  - reponse ok => ApiResult parse.
 */
export async function analyzeListing(
  rawText: string,
  imageUrls: string[],
): Promise<ApiResult> {
  const body = buildAnalyzeBody(rawText, imageUrls);
  const res = await fetch(`${getApiUrl()}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    let detail: string | undefined;
    try {
      const payload = (await res.json()) as { detail?: unknown };
      if (typeof payload.detail === 'string' && payload.detail.length > 0) {
        detail = payload.detail;
      }
    } catch {
      // corps non JSON : on retombe sur le statut HTTP plus bas
    }
    throw new Error(detail ?? `HTTP ${res.status}`);
  }

  return (await res.json()) as ApiResult;
}
