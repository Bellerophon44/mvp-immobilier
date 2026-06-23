/**
 * Construit le JavaScript injecte dans la WebView pour extraire le contenu de
 * l'annonce ouverte. SPEC mobile-phase2-tranche1 §4.2 (famille B, verifiee sur
 * device, pas en sandbox).
 *
 * Important (exigence de la revue, leçon mobile-phase2-tranche1) : ce script NE
 * filtre PAS les images par rule/host. Il collecte TOUTES les URLs d'images
 * brutes (http(s) uniquement) ; le filtrage (host strict, rule=ad-large, dedup,
 * cap 50) est la responsabilite de filterGallery (src/lib/gallery.ts), SOURCE
 * UNIQUE DE VERITE cote RN. Dupliquer le filtrage ici ferait diverger le code
 * reellement execute sur device du code teste.
 *
 * Le script : scrolle pour declencher le lazy-load de la galerie, attend, puis
 * collecte document.body.innerText + les URLs d'images brutes (src + plus grande
 * candidate de srcset), et renvoie le tout au natif via postMessage. En cas
 * d'erreur : postMessage({ ok:false, error }).
 */

const SCROLL_WAIT_MS = 1500;

export function buildInjectedScript(): string {
  return `
(function () {
  try {
    window.scrollTo(0, document.body.scrollHeight);
    setTimeout(function () {
      var text = document.body.innerText || '';
      var rawImageUrls = Array.prototype.slice
        .call(document.querySelectorAll('img'))
        .map(function (i) {
          // plus grande candidate de srcset si present, sinon src
          return i.srcset ? i.srcset.split(',').pop().trim().split(' ')[0] : i.src;
        })
        .filter(function (u) {
          return typeof u === 'string' && /^https?:\\/\\//i.test(u);
        });
      window.ReactNativeWebView.postMessage(JSON.stringify({
        ok: true,
        text: text,
        rawImageUrls: rawImageUrls
      }));
    }, ${SCROLL_WAIT_MS});
  } catch (e) {
    window.ReactNativeWebView.postMessage(JSON.stringify({ ok: false, error: String(e) }));
  }
  true;
})();
`;
}
