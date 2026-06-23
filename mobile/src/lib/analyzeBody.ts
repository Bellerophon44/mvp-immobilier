/** Corps du POST /analyze consomme par le backend Phase 1 (mode raw_text). */
export interface AnalyzeBody {
  raw_text: string;
  image_urls?: string[];
}

/**
 * Construit le corps du POST /analyze. SPEC mobile-phase2-tranche1 §5.A (AC9-AC10) :
 *  - raw_text = le texte de l'annonce ;
 *  - image_urls = la galerie filtree ; OMETTRE la cle si la galerie est vide ;
 *  - ne JAMAIS emettre de champ 'url' (le backend l'extraierait via fetch HTML).
 */
export function buildAnalyzeBody(_rawText: string, _imageUrls: string[]): AnalyzeBody {
  throw new Error('NOT_IMPLEMENTED: buildAnalyzeBody');
}
