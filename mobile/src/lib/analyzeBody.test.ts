import { buildAnalyzeBody } from './analyzeBody';
import * as fs from 'fs';
import * as path from 'path';

// Oracle : SPEC mobile-phase2-tranche1 §3.4 + §4.3 + §5.A (AC9), GATE 2 decision 3
// (galerie vide -> OMETTRE la cle image_urls). Lecon mobile-phase1-image-urls /
// cross-agence-inc2b : prouver le CONTENU EXACT transmis et l ABSENCE de cle, pas
// "un body est produit". On utilise not.toHaveProperty (PAS toEqual([])).
//
// Falsifiabilite : stub `throw NOT_IMPLEMENTED: buildAnalyzeBody` -> tous rouges
// pour la bonne raison ; deviendront verts a l implementation, sans reecriture.
describe('buildAnalyzeBody (AC9)', () => {
  // AC9 : galerie NON vide -> { raw_text, image_urls } exact (deep-equals).
  it('AC9 : galerie non vide -> raw_text + image_urls exacts', () => {
    const body = buildAnalyzeBody('Appartement T3 ...', [
      'https://img.leboncoin.fr/x.jpg?rule=ad-large',
    ]);
    expect(body).toEqual({
      raw_text: 'Appartement T3 ...',
      image_urls: ['https://img.leboncoin.fr/x.jpg?rule=ad-large'],
    });
  });

  // AC9 : image_urls deep-equals la liste EXACTE (ordre + valeurs), pas filtree/triee.
  it('AC9 : image_urls preserve la liste exacte (ordre + valeurs)', () => {
    const urls = [
      'https://img.leboncoin.fr/api/v1/img/A.jpg?rule=ad-large',
      'https://img.leboncoin.fr/api/v1/img/B.jpg?rule=ad-large',
      'https://img.leboncoin.fr/api/v1/img/C.jpg?rule=ad-large',
    ];
    const body = buildAnalyzeBody('texte', urls);
    expect(body.image_urls).toEqual(urls);
  });

  // AC9 (raw_text exact) : le texte est transmis tel quel, octet pour octet.
  it('AC9 : raw_text transmis exactement (non altere)', () => {
    const txt = 'Maison 5 pieces\n120 m2\nPrix : 250 000 EUR';
    const body = buildAnalyzeBody(txt, [
      'https://img.leboncoin.fr/x.jpg?rule=ad-large',
    ]);
    expect(body.raw_text).toBe(txt);
  });

  // AC9 (decision GATE 2 n3) : galerie VIDE -> la cle image_urls est ABSENTE.
  // Assertion explicite not.toHaveProperty (pas toEqual([])) : prouver l absence.
  it('AC9 : galerie vide -> PAS de cle image_urls', () => {
    const body = buildAnalyzeBody('Appartement T3 ...', []);
    expect(body).not.toHaveProperty('image_urls');
    expect(body.raw_text).toBe('Appartement T3 ...');
  });

  it('AC9 : galerie vide -> body strictement egal a { raw_text }', () => {
    const body = buildAnalyzeBody('texte seul', []);
    expect(body).toEqual({ raw_text: 'texte seul' });
  });

  // AC9 / §3.4 (anti-fetch serveur) : le body ne contient JAMAIS la cle 'url'.
  // Assertion explicite : on POSTe le texte extrait on-device, pas l URL.
  it('AC9 : le body ne contient JAMAIS la cle url (galerie non vide)', () => {
    const body = buildAnalyzeBody('texte', [
      'https://img.leboncoin.fr/x.jpg?rule=ad-large',
    ]);
    expect(body).not.toHaveProperty('url');
  });

  it('AC9 : le body ne contient JAMAIS la cle url (galerie vide)', () => {
    const body = buildAnalyzeBody('texte', []);
    expect(body).not.toHaveProperty('url');
  });

  // AC9 : aucune cle parasite. Les seules cles autorisees sont raw_text et image_urls.
  it('AC9 : aucune cle parasite (seules raw_text / image_urls autorisees)', () => {
    const body = buildAnalyzeBody('texte', [
      'https://img.leboncoin.fr/x.jpg?rule=ad-large',
    ]);
    expect(Object.keys(body).sort()).toEqual(['image_urls', 'raw_text']);
  });
});

// AC12 (volet logique pure disponible dans ce perimetre) : aucune URL backend en
// dur ni secret dans les modules purs src/lib/*.ts. La config (EXPO_PUBLIC_API_URL)
// et la couche reseau (analyzeListing/fetch) sont HORS des 3 stubs de cette tranche
// (pas 5 de la spec, modules non encore crees) : AC10/AC11 et le volet config.ts
// d AC12 sont signales en rapport comme hors perimetre testable ici.
// Ce test statique verrouille des MAINTENANT l invariant "pas de secret/URL en dur"
// sur la logique pure existante (il est VERT immediatement : il ne depend d aucun
// stub et echouerait si un de ces modules introduisait une URL fly.dev / une cle).
describe('AC12 (statique) : pas d URL backend ni de secret en dur dans src/lib', () => {
  const libDir = __dirname;
  const sources = fs
    .readdirSync(libDir)
    .filter((f) => f.endsWith('.ts') && !f.endsWith('.test.ts'));

  it.each(sources)('%s ne contient pas d URL backend codee en dur', (file) => {
    const content = fs.readFileSync(path.join(libDir, file), 'utf8');
    expect(content).not.toMatch(/fly\.dev/);
    expect(content).not.toMatch(/coherence-metz\.fr/);
    expect(content).not.toMatch(/coherence-staging/);
  });

  it.each(sources)('%s ne contient pas de chaine ressemblant a une cle API', (file) => {
    const content = fs.readFileSync(path.join(libDir, file), 'utf8');
    // cle OpenAI (sk-...) ou Google (AIza...) : ne doivent jamais etre embarquees.
    expect(content).not.toMatch(/sk-[A-Za-z0-9]{16,}/);
    expect(content).not.toMatch(/AIza[A-Za-z0-9_-]{16,}/);
  });
});
