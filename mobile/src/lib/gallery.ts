/** Cap d'entree cote app, aligne sur MAX_INPUT_IMAGE_URLS serveur. SPEC AC8. */
export const MAX_INPUT_IMAGE_URLS = 50;

/**
 * Filtre/normalise les URLs d'images collectees dans le DOM pour ne garder que
 * la GALERIE du bien. SPEC mobile-phase2-tranche1 §5.A (AC5-AC8) :
 *  - ne garder que les images en rule=ad-large ;
 *  - exclure ad-image (annonces similaires), bo-* (logos), pp-small (promos) ;
 *  - dedupliquer par chemin d'image (origin + pathname) ;
 *  - normaliser en ?rule=ad-large ;
 *  - capper a MAX_INPUT_IMAGE_URLS (les 50 premieres).
 */
export function filterGallery(_rawUrls: string[]): string[] {
  throw new Error('NOT_IMPLEMENTED: filterGallery');
}
