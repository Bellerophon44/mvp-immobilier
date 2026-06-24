/** Cap d'entree cote app, aligne sur MAX_INPUT_IMAGE_URLS serveur. SPEC AC8. */
export const MAX_INPUT_IMAGE_URLS = 50;

/** Hosts CDN d'images conserves. Un seul cable pour cette tranche (LBC). SPEC D-IMAGE-HOSTS. */
const IMAGE_HOSTS = ['img.leboncoin.fr'];

/**
 * Filtre/normalise les URLs d'images collectees dans le DOM pour ne garder que
 * la GALERIE du bien. SPEC mobile-phase2-tranche1 §5.A (AC5-AC8) :
 *  - ne garder que les images en rule=ad-large ;
 *  - exclure ad-image (annonces similaires), bo-* (logos), pp-small (promos) ;
 *  - dedupliquer par chemin d'image (origin + pathname) ;
 *  - normaliser en ?rule=ad-large ;
 *  - capper a MAX_INPUT_IMAGE_URLS (les 50 premieres).
 */
export function filterGallery(rawUrls: string[]): string[] {
  const seen = new Set<string>();
  const gallery: string[] = [];
  for (const raw of rawUrls) {
    if (gallery.length >= MAX_INPUT_IMAGE_URLS) {
      break;
    }
    let parsed: URL;
    try {
      parsed = new URL(raw);
    } catch {
      continue;
    }
    if (!IMAGE_HOSTS.some((h) => parsed.hostname === h)) {
      continue;
    }
    if (parsed.searchParams.get('rule') !== 'ad-large') {
      continue;
    }
    const id = parsed.origin + parsed.pathname;
    if (seen.has(id)) {
      continue;
    }
    seen.add(id);
    gallery.push(parsed.origin + parsed.pathname + '?rule=ad-large');
  }
  return gallery;
}
