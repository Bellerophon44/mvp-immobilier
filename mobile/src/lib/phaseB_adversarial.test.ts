import { firstUrl } from './extractUrl';
import { filterGallery, MAX_INPUT_IMAGE_URLS } from './gallery';
import { buildAnalyzeBody } from './analyzeBody';

// =====================================================================
// PHASE B — tests adversariaux (TESTEUR). Cherchent activement les faux-verts
// et trous des AC1-AC9. On asserte le RESULTAT REEL (liste/borne/valeur exacte),
// jamais "non vide" ni "ne plante pas". Lecons : prouver le contenu exact, bornes
// exactes, listes EXACTES (cross-agence-inc2b, mobile-phase1, 9.7, issue-100-B).
//
// Falsifiabilite : chaque assertion-cle a ete prouvee rougissante par mutation
// locale du code produit puis restauree a l'identique (mutations decrites en
// commentaire au-dessus du test ; voir aussi le rapport phase B).
// =====================================================================

describe('PhaseB firstUrl — ponctuation finale / query / fragment / multi-lignes', () => {
  // L'URL de partage LBC reelle est suivie d'un ESPACE -> capture propre.
  // Falsifiable : rougit si la regex passe a [^\s.]+ ou capture l'espace.
  it('URL en milieu de phrase suivie d un espace -> URL propre, sans ponctuation', () => {
    expect(
      firstUrl(
        'voir https://www.leboncoin.fr/ad/ventes_immobilieres/3205520874 merci !',
      ),
    ).toBe('https://www.leboncoin.fr/ad/ventes_immobilieres/3205520874');
  });

  // Query + fragment SANS espace : conserves entiers (jusqu au 1er espace).
  it('URL avec query (?) et fragment (#) -> capturee entiere jusqu au 1er espace', () => {
    expect(
      firstUrl('lien https://www.leboncoin.fr/ad/x?foo=1&bar=2#galerie suite'),
    ).toBe('https://www.leboncoin.fr/ad/x?foo=1&bar=2#galerie');
  });

  // Multi-lignes : le \n borne la capture (\s inclut le retour a la ligne).
  it('texte multi-lignes -> la 1ere URL bornee par le retour a la ligne', () => {
    expect(firstUrl('ligne1\nhttps://www.leboncoin.fr/ad/42\nligne3')).toBe(
      'https://www.leboncoin.fr/ad/42',
    );
  });

  // Separateur tabulation : \t borne aussi la capture.
  it('separateur tabulation -> URL bornee par la tabulation', () => {
    expect(firstUrl('a\thttps://www.leboncoin.fr/ad/7\tb')).toBe(
      'https://www.leboncoin.fr/ad/7',
    );
  });

  // LIMITE CONNUE (documentee, non bloquante) : une ponctuation/guillemet COLLE
  // (sans espace) a l URL est capture par la regex de reference [^\s]+. La spec
  // §4.1 prescrit EXACTEMENT cette regex (jusqu au 1er espace) ; le cas LBC reel
  // (URL suivie d un espace) est propre. On FIGE ce comportement pour qu un futur
  // changement de regex soit un choix conscient, pas une regression silencieuse.
  it('LIMITE : ponctuation collee sans espace -> incluse (comportement spike fige)', () => {
    // guillemet + virgule colles : capture parasite assumee (cf. rapport).
    expect(firstUrl('"https://un.example/x", suite')).toBe(
      'https://un.example/x",',
    );
  });
});

describe('PhaseB filterGallery — hosts malveillants (matching STRICT, pas includes)', () => {
  // Faille classique : un filtre host en `url.indexOf(host) !== -1` (comme le
  // SPIKE App.js l.53) laisserait passer ces hosts. Le code produit compare
  // `hostname === host` -> doit REJETER. Falsifiable : repasser a un includes
  // (ou `endsWith`) rendrait ces 3 tests rouges.
  it('host suffixe img.leboncoin.fr.evil.com -> REJETE', () => {
    expect(
      filterGallery([
        'https://img.leboncoin.fr.evil.com/api/v1/img/A.jpg?rule=ad-large',
      ]),
    ).toEqual([]);
  });

  it('host prefixe evil-img.leboncoin.fr -> REJETE', () => {
    expect(
      filterGallery([
        'https://evil-img.leboncoin.fr/api/v1/img/A.jpg?rule=ad-large',
      ]),
    ).toEqual([]);
  });

  it('sous-domaine a.img.leboncoin.fr -> REJETE (egalite stricte)', () => {
    expect(
      filterGallery([
        'https://a.img.leboncoin.fr/api/v1/img/A.jpg?rule=ad-large',
      ]),
    ).toEqual([]);
  });

  // Contraste : le host EXACT, lui, passe (prouve que le rejet ci-dessus n est
  // pas un faux-vert "tout est rejete").
  it('contraste : host EXACT img.leboncoin.fr -> garde', () => {
    expect(
      filterGallery([
        'https://img.leboncoin.fr/api/v1/img/A.jpg?rule=ad-large',
      ]),
    ).toEqual(['https://img.leboncoin.fr/api/v1/img/A.jpg?rule=ad-large']);
  });
});

describe('PhaseB filterGallery — URLs non parsables / protocoles speciaux (pas de crash)', () => {
  // Entrees pieges melangees a une URL valide : ne doivent pas planter ni polluer,
  // et l URL valide doit survivre (ordre preserve). Falsifiable : un `new URL`
  // hors try, ou un host-match permissif, casserait ce test.
  it('data: / blob: / vide / non-url ignorees, URL valide conservee', () => {
    const input = [
      'data:image/png;base64,AAAA',
      'blob:https://img.leboncoin.fr/uuid-1234',
      '',
      'pas une url du tout',
      '//img.leboncoin.fr/api/v1/img/proto-relatif.jpg?rule=ad-large',
      'https://img.leboncoin.fr/api/v1/img/VALIDE.jpg?rule=ad-large',
    ];
    expect(filterGallery(input)).toEqual([
      'https://img.leboncoin.fr/api/v1/img/VALIDE.jpg?rule=ad-large',
    ]);
  });

  it('liste 100% pieges -> [] (jamais d exception)', () => {
    expect(() =>
      filterGallery(['data:x', 'blob:y', '', '???', 'ftp://x/y?rule=ad-large']),
    ).not.toThrow();
    expect(
      filterGallery(['data:x', 'blob:y', '', '???', 'ftp://x/y?rule=ad-large']),
    ).toEqual([]);
  });
});

describe('PhaseB filterGallery — normalisation query parasite', () => {
  // ad-large AVEC d autres params -> ressort en ?rule=ad-large propre (un seul
  // param). Falsifiable : si la normalisation gardait la query brute, la sortie
  // contiendrait foo=bar / w=800.
  it('rule=ad-large&foo=bar -> normalise en ?rule=ad-large seul', () => {
    expect(
      filterGallery([
        'https://img.leboncoin.fr/api/v1/img/X.jpg?rule=ad-large&foo=bar',
      ]),
    ).toEqual(['https://img.leboncoin.fr/api/v1/img/X.jpg?rule=ad-large']);
  });

  it('foo=bar&rule=ad-large (rule en 2e position) -> reconnu et normalise', () => {
    expect(
      filterGallery([
        'https://img.leboncoin.fr/api/v1/img/X.jpg?foo=bar&rule=ad-large',
      ]),
    ).toEqual(['https://img.leboncoin.fr/api/v1/img/X.jpg?rule=ad-large']);
  });
});

describe('PhaseB filterGallery — ordre & dedup cross-rule de la MEME photo', () => {
  // La MEME photo P arrive en ad-large PUIS ad-thumb PUIS ad-image, entrelacee
  // avec Q (ad-large) et R (ad-large). Attendu : P, Q, R dans l ordre de 1ere
  // apparition de leur variante ad-large ; une seule entree normalisee par chemin.
  // Falsifiable : un tri, ou une dedup comptant la query, casserait l ordre/cardinalite.
  it('P(large,thumb,image) entrelace Q,R -> [P,Q,R] ordre 1ere apparition ad-large', () => {
    const input = [
      'https://img.leboncoin.fr/api/v1/img/P.jpg?rule=ad-large',
      'https://img.leboncoin.fr/api/v1/img/Q.jpg?rule=ad-large',
      'https://img.leboncoin.fr/api/v1/img/P.jpg?rule=ad-thumb',
      'https://img.leboncoin.fr/api/v1/img/R.jpg?rule=ad-large',
      'https://img.leboncoin.fr/api/v1/img/P.jpg?rule=ad-image',
      'https://img.leboncoin.fr/api/v1/img/Q.jpg?rule=ad-large&w=99',
    ];
    expect(filterGallery(input)).toEqual([
      'https://img.leboncoin.fr/api/v1/img/P.jpg?rule=ad-large',
      'https://img.leboncoin.fr/api/v1/img/Q.jpg?rule=ad-large',
      'https://img.leboncoin.fr/api/v1/img/R.jpg?rule=ad-large',
    ]);
  });

  // RGPD / faux photo_status : une photo qui n existe QU EN ad-image (annonce
  // SIMILAIRE, autre bien) ne doit JAMAIS entrer dans la galerie -> sinon le
  // backend evaluerait un claim sur la photo d un AUTRE bien. Falsifiable : si le
  // filtre rule etait retire, S.jpg entrerait.
  it('photo presente UNIQUEMENT en ad-image (autre bien) -> JAMAIS dans la galerie', () => {
    const input = [
      'https://img.leboncoin.fr/api/v1/img/S.jpg?rule=ad-image',
      'https://img.leboncoin.fr/api/v1/img/T.jpg?rule=ad-large',
    ];
    expect(filterGallery(input)).toEqual([
      'https://img.leboncoin.fr/api/v1/img/T.jpg?rule=ad-large',
    ]);
  });
});

describe('PhaseB filterGallery — cap 50 : ad-image ne consomment PAS le budget', () => {
  // 60 ad-large DISTINCTES melangees a des ad-image. Le cap doit s appliquer aux
  // 50 PREMIERES ad-large ; les ad-image (exclues) ne doivent pas remplir le budget
  // a la place d ad-large valides. Falsifiable : si le cap testait gallery.length
  // APRES un push naif des ad-image, on perdrait des ad-large valides.
  it('60 ad-large distinctes entrelacees d ad-image -> 50 premieres ad-large', () => {
    const input: string[] = [];
    for (let i = 0; i < 60; i++) {
      input.push(
        `https://img.leboncoin.fr/api/v1/img/large${i}.jpg?rule=ad-large`,
      );
      input.push(
        `https://img.leboncoin.fr/api/v1/img/img${i}.jpg?rule=ad-image`,
      );
    }
    const out = filterGallery(input);
    expect(out).toHaveLength(50);
    expect(out[0]).toBe(
      'https://img.leboncoin.fr/api/v1/img/large0.jpg?rule=ad-large',
    );
    expect(out[49]).toBe(
      'https://img.leboncoin.fr/api/v1/img/large49.jpg?rule=ad-large',
    );
    // large50 (la 51e ad-large) exclue ; aucune ad-image dans la sortie.
    expect(out).not.toContain(
      'https://img.leboncoin.fr/api/v1/img/large50.jpg?rule=ad-large',
    );
    expect(out.some((u) => u.includes('img0.jpg'))).toBe(false);
  });

  // Le cap compte les ENTREES UNIQUES, pas les occurrences brutes : 50 chemins
  // distincts chacun duplique 2x (100 entrees) -> 50 en sortie (la dedup precede
  // le cap). Falsifiable : un cap sur le nombre d entrees brutes traitees
  // donnerait < 50 (25 chemins).
  it('50 chemins distincts dupliques (100 entrees) -> 50 uniques (dedup avant cap)', () => {
    const input: string[] = [];
    for (let i = 0; i < 50; i++) {
      const u = `https://img.leboncoin.fr/api/v1/img/d${i}.jpg?rule=ad-large`;
      input.push(u);
      input.push(u);
    }
    expect(filterGallery(input)).toHaveLength(50);
  });
});

describe('PhaseB filterGallery — non-mutation de l entree', () => {
  // filterGallery ne doit pas muter le tableau recu (ni son contenu).
  it('le tableau d entree est inchange apres l appel', () => {
    const input = [
      'https://img.leboncoin.fr/api/v1/img/A.jpg?rule=ad-large',
      'https://img.leboncoin.fr/api/v1/img/B.jpg?rule=ad-image',
    ];
    const snapshot = [...input];
    filterGallery(input);
    expect(input).toEqual(snapshot);
  });
});

describe('PhaseB buildAnalyzeBody — invariants de transit', () => {
  // raw_text vide DOIT rester present (cle raw_text avec valeur "") : le backend
  // arbitre 400 si vraiment aucun input. Falsifiable : si la fonction omettait
  // raw_text vide, ce test rougit.
  it('raw_text vide -> body = { raw_text: "" } (cle presente, valeur vide)', () => {
    expect(buildAnalyzeBody('', [])).toEqual({ raw_text: '' });
  });

  // buildAnalyzeBody ne mute pas le tableau d images recu.
  it('ne mute pas le tableau image_urls recu', () => {
    const urls = [
      'https://img.leboncoin.fr/a.jpg?rule=ad-large',
      'https://img.leboncoin.fr/b.jpg?rule=ad-large',
    ];
    const snapshot = [...urls];
    buildAnalyzeBody('t', urls);
    expect(urls).toEqual(snapshot);
  });

  // Aucune cle parasite ni 'url' meme avec une galerie d 1 element.
  it('exactement les cles autorisees, jamais de cle url ni parasite', () => {
    const body = buildAnalyzeBody('t', [
      'https://img.leboncoin.fr/a.jpg?rule=ad-large',
    ]);
    expect(Object.keys(body).sort()).toEqual(['image_urls', 'raw_text']);
    expect(body).not.toHaveProperty('url');
  });
});
