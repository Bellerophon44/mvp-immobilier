import { filterGallery, MAX_INPUT_IMAGE_URLS } from './gallery';

// Oracle : SPEC mobile-phase2-tranche1 §4.2 + §5.A (AC5-AC8), logique de reference
// spikes/lbc-extraction/App.js (buildExtractor : byRule/seen/gallery).
// Regle metier : ne garder que rule=ad-large ; exclure ad-image / bo-* / pp-small /
// ad-thumb / aucune-rule ; dedup par (origin+pathname) ; normaliser en
// `origin+pathname+'?rule=ad-large'` ; ordre de 1ere apparition ; cap a 50.
//
// Falsifiabilite : stub `throw NOT_IMPLEMENTED: filterGallery` -> tous rouges
// pour la bonne raison. On asserte la LISTE EXACTE (ordre + valeurs), jamais
// "non vide". Lecon mobile-phase1 / cross-agence-inc2b : prouver le contenu exact.
describe('filterGallery (AC5-AC8)', () => {
  // AC8 (constante) : le cap cote app est aligne sur le serveur (= 50).
  it('AC8 : MAX_INPUT_IMAGE_URLS vaut exactement 50', () => {
    expect(MAX_INPUT_IMAGE_URLS).toBe(50);
  });

  // AC5 : melange realiste de rules -> ne garde QUE l unique ad-large, normalisee.
  it('AC5 : garde ad-large, exclut ad-image / bo-* / pp-small / ad-thumb / sans-rule', () => {
    const input = [
      'https://img.leboncoin.fr/api/v1/img/A.jpg?rule=ad-large', // galerie -> gardee
      'https://img.leboncoin.fr/api/v1/img/B.jpg?rule=ad-image', // annonces similaires -> exclue
      'https://img.leboncoin.fr/api/v1/img/C.jpg?rule=bo-thumb', // logo agence -> exclue
      'https://img.leboncoin.fr/api/v1/img/D.jpg?rule=pp-small', // promo -> exclue
      'https://img.leboncoin.fr/api/v1/img/E.jpg?rule=ad-thumb', // vignette -> exclue
      'https://img.leboncoin.fr/api/v1/img/F.jpg', // sans rule -> exclue
    ];
    expect(filterGallery(input)).toEqual([
      'https://img.leboncoin.fr/api/v1/img/A.jpg?rule=ad-large',
    ]);
  });

  // AC5 (bord) : que des rules exclues -> liste vide exacte (pas une fuite).
  it('AC5 : entree 100% exclue (aucune ad-large) -> []', () => {
    const input = [
      'https://img.leboncoin.fr/api/v1/img/B.jpg?rule=ad-image',
      'https://img.leboncoin.fr/api/v1/img/C.jpg?rule=bo-logo',
      'https://img.leboncoin.fr/api/v1/img/D.jpg?rule=pp-small',
      'https://img.leboncoin.fr/api/v1/img/E.jpg?rule=ad-thumb',
      'https://img.leboncoin.fr/api/v1/img/F.jpg',
    ];
    expect(filterGallery(input)).toEqual([]);
  });

  // AC6 : un host hors CDN (img.leboncoin.fr) est exclu MEME en rule=ad-large.
  it('AC6 : host non-CDN en ad-large -> exclu, ne pollue pas la galerie LBC', () => {
    const input = [
      'https://www.googletagmanager.com/x.png?rule=ad-large', // hors CDN -> exclue
      'https://img.leboncoin.fr/api/v1/img/A.jpg?rule=ad-large', // CDN -> gardee
    ];
    expect(filterGallery(input)).toEqual([
      'https://img.leboncoin.fr/api/v1/img/A.jpg?rule=ad-large',
    ]);
  });

  // AC6 (bord) : que des hosts hors CDN -> [].
  it('AC6 : entree 100% hors CDN (meme ad-large) -> []', () => {
    const input = [
      'https://www.googletagmanager.com/x.png?rule=ad-large',
      'https://cdn.autre-portail.com/y.jpg?rule=ad-large',
    ];
    expect(filterGallery(input)).toEqual([]);
  });

  // AC7 : meme photo en plusieurs tailles/formes -> dedup par origin+pathname,
  // normalisee, ordre de 1ere apparition. P (3 formes) -> 1 ; Q -> 1. Total = 2.
  it('AC7 : dedup par chemin + normalisation ad-large (2 URLs, pas 1, pas 4)', () => {
    const input = [
      'https://img.leboncoin.fr/api/v1/img/P.jpg?rule=ad-large',
      'https://img.leboncoin.fr/api/v1/img/P.jpg?rule=ad-thumb', // meme chemin, autre rule -> exclue (pas ad-large)
      'https://img.leboncoin.fr/api/v1/img/P.jpg?rule=ad-large&w=800', // meme chemin, query differente -> doublon
      'https://img.leboncoin.fr/api/v1/img/Q.jpg?rule=ad-large',
    ];
    expect(filterGallery(input)).toEqual([
      'https://img.leboncoin.fr/api/v1/img/P.jpg?rule=ad-large',
      'https://img.leboncoin.fr/api/v1/img/Q.jpg?rule=ad-large',
    ]);
  });

  // AC7 (anti-faux-vert) : la dedup ne doit PAS compter la query string. Deux URLs
  // ad-large de meme chemin mais query differente => 1 seule sortie.
  it('AC7 : deux ad-large de meme chemin, query differente -> 1 seule (dedup par chemin)', () => {
    const input = [
      'https://img.leboncoin.fr/api/v1/img/P.jpg?rule=ad-large&w=300',
      'https://img.leboncoin.fr/api/v1/img/P.jpg?rule=ad-large&w=1200',
    ];
    expect(filterGallery(input)).toEqual([
      'https://img.leboncoin.fr/api/v1/img/P.jpg?rule=ad-large',
    ]);
  });

  // AC8 (borne basse exacte) : 50 chemins ad-large distincts -> 50 conserves.
  it('AC8 : 50 ad-large distinctes -> 50 conservees (ordre de 1ere apparition)', () => {
    const input = Array.from(
      { length: 50 },
      (_v, i) =>
        `https://img.leboncoin.fr/api/v1/img/photo${i}.jpg?rule=ad-large`,
    );
    const expected = Array.from(
      { length: 50 },
      (_v, i) =>
        `https://img.leboncoin.fr/api/v1/img/photo${i}.jpg?rule=ad-large`,
    );
    const out = filterGallery(input);
    expect(out).toHaveLength(50);
    expect(out).toEqual(expected);
  });

  // AC8 (borne haute exacte, off-by-one) : 51 distinctes -> tronque a 50, ce sont
  // les 50 PREMIERES (photo0..photo49) ; photo50 exclue.
  it('AC8 : 51 ad-large distinctes -> tronque aux 50 PREMIERES (51e exclue)', () => {
    const input = Array.from(
      { length: 51 },
      (_v, i) =>
        `https://img.leboncoin.fr/api/v1/img/photo${i}.jpg?rule=ad-large`,
    );
    const out = filterGallery(input);
    expect(out).toHaveLength(50);
    expect(out[0]).toBe(
      'https://img.leboncoin.fr/api/v1/img/photo0.jpg?rule=ad-large',
    );
    expect(out[49]).toBe(
      'https://img.leboncoin.fr/api/v1/img/photo49.jpg?rule=ad-large',
    );
    // la 51e (photo50) ne doit PAS etre dans la sortie.
    expect(out).not.toContain(
      'https://img.leboncoin.fr/api/v1/img/photo50.jpg?rule=ad-large',
    );
  });

  // AC8 (bord) : galerie absente (page d accueil LBC, spike Niveau 2) -> [].
  it('AC8 : aucune ad-large (page accueil) -> []', () => {
    expect(filterGallery([])).toEqual([]);
    expect(
      filterGallery([
        'https://img.leboncoin.fr/api/v1/img/banner.jpg?rule=ad-image',
      ]),
    ).toEqual([]);
  });
});
