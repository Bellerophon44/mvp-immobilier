import { firstUrl } from './extractUrl';

// Oracle : SPEC mobile-phase2-tranche1 §4.1 + §5.A (AC1-AC4).
// Regex de reference du spike : /https?:\/\/[^\s]+/i (1ere URL, jusqu'au 1er espace).
// Falsifiabilite : aujourd'hui le stub `throw new Error('NOT_IMPLEMENTED: firstUrl')`
// -> chaque test ci-dessous est ROUGE pour la BONNE raison (impl manquante).
// Deviendront verts quand le dev portera la regex du spike, SANS reecriture de test.
//
// On asserte la VALEUR EXACTE retournee (jamais "verite/non-null") : lecon 9.7
// (bornes exactes) + lecon mobile-phase1 (prouver le contenu, pas l'absence d'erreur).
describe('firstUrl (AC1-AC4)', () => {
  // AC1 : texte + URL (partage iOS reel) -> extrait EXACTEMENT l'URL, sans le texte
  // de gauche ni l'espace + suffixe a droite.
  it('AC1 : "texte ... leboncoin: <url> suffixe" -> l URL exacte (sans espace)', () => {
    const input =
      'Voici une annonce sur leboncoin: https://www.leboncoin.fr/ad/ventes_immobilieres/123 super';
    expect(firstUrl(input)).toBe(
      'https://www.leboncoin.fr/ad/ventes_immobilieres/123',
    );
  });

  // AC1bis : forme exacte du libelle de partage cite dans la mission/spec §4.1.
  it('AC1 : partage iOS reel "Voici une annonce ... sur leboncoin: <url>" -> url exacte', () => {
    const input =
      'Voici une annonce qui pourrait vous interesser sur leboncoin: https://www.leboncoin.fr/ad/ventes_immobilieres/3205520874';
    expect(firstUrl(input)).toBe(
      'https://www.leboncoin.fr/ad/ventes_immobilieres/3205520874',
    );
  });

  // AC2 : URL nue -> elle-meme, octet pour octet.
  it('AC2 : URL nue https -> renvoyee telle quelle', () => {
    const u = 'https://www.leboncoin.fr/ad/ventes_immobilieres/456';
    expect(firstUrl(u)).toBe(u);
  });

  // AC2 : variante http (non-https) acceptee.
  it('AC2 : URL nue http (non securisee) -> renvoyee telle quelle', () => {
    const u = 'http://www.leboncoin.fr/ad/ventes_immobilieres/789';
    expect(firstUrl(u)).toBe(u);
  });

  // AC2 : insensible a la casse du schema (regex /i). HTTPS:// doit etre capte.
  it('AC2 : schema en majuscules HTTPS:// -> capte (regex insensible a la casse)', () => {
    const u = 'HTTPS://www.leboncoin.fr/ad/ventes_immobilieres/999';
    expect(firstUrl(u)).toBe(u);
  });

  // AC3 : plusieurs URLs -> la PREMIERE exactement (jamais la 2e, jamais concatenee).
  it('AC3 : deux URLs separees par du texte -> la 1ere exacte', () => {
    expect(firstUrl('a https://un.example/x b https://deux.example/y')).toBe(
      'https://un.example/x',
    );
  });

  // AC3 : sonde anti-concatenation -> la sortie ne doit pas contenir la 2e URL.
  it('AC3 : la sortie n inclut jamais la 2e URL', () => {
    const out = firstUrl('a https://un.example/x b https://deux.example/y');
    expect(out).not.toContain('deux.example');
  });

  // AC4 : aucune URL -> null (pas "", pas undefined, pas d exception).
  it('AC4 : texte sans lien -> null', () => {
    expect(firstUrl('juste du texte sans lien')).toBeNull();
  });

  // AC4 : chaine vide -> null.
  it('AC4 : chaine vide -> null', () => {
    expect(firstUrl('')).toBeNull();
  });

  // AC4 : entrees nullish (le partage natif peut fournir undefined/null) -> null,
  // PAS d exception. Le spike protege par `(s || '')`. On contourne le typage strict
  // (param `string`) par un cast cible : on teste la robustesse RUNTIME documentee
  // par la spec, sans toucher au stub.
  it('AC4 : undefined -> null (pas d exception)', () => {
    const f = firstUrl as (x: unknown) => string | null;
    expect(f(undefined)).toBeNull();
  });

  it('AC4 : null -> null (pas d exception)', () => {
    const f = firstUrl as (x: unknown) => string | null;
    expect(f(null)).toBeNull();
  });
});
