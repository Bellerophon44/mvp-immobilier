import { ApiResult } from './types';

/**
 * Appelle POST {getApiUrl()}/analyze en mode raw_text (SPEC AC10/AC11) :
 *  - corps = buildAnalyzeBody(rawText, imageUrls) (raw_text + image_urls, jamais url) ;
 *  - en-tete Content-Type: application/json, methode POST ;
 *  - reponse non-ok => rejet avec le detail backend (pas de faux succes) ;
 *  - reponse ok => ApiResult parse.
 */
export async function analyzeListing(
  _rawText: string,
  _imageUrls: string[],
): Promise<ApiResult> {
  throw new Error('NOT_IMPLEMENTED: analyzeListing');
}
