import { getApiUrl } from './config';

// =====================================================================
// PHASE A — tests-first (TESTEUR). SPEC mobile-phase2-tranche1 §5.A AC12
// (volet DYNAMIQUE / config). Cible : src/lib/config.ts
// (stub `throw NOT_IMPLEMENTED: getApiUrl`). ROUGES maintenant, verts apres impl.
//
// NB : le volet STATIQUE d'AC12 (aucune URL backend ni cle API en dur dans
// src/lib/*.ts) est DEJA couvert par les `it.each` de analyzeBody.test.ts qui
// scannent tous les modules — NON duplique ici (lecon : pas de cardinalite/scan
// redondant).
//
// process.env.EXPO_PUBLIC_API_URL set/restore par test pour isolation (lecon 9.7 :
// pas d'etat partage qui fuit entre tests).
// =====================================================================

const savedApiUrl = process.env.EXPO_PUBLIC_API_URL;

afterEach(() => {
  if (savedApiUrl === undefined) {
    delete process.env.EXPO_PUBLIC_API_URL;
  } else {
    process.env.EXPO_PUBLIC_API_URL = savedApiUrl;
  }
});

describe('getApiUrl — AC12 (config) : lit EXPO_PUBLIC_API_URL', () => {
  // AC12 : getApiUrl() renvoie EXACTEMENT la valeur de process.env.EXPO_PUBLIC_API_URL.
  // Falsifiable : echoue si getApiUrl renvoie une URL en dur (ex. fly.dev) au lieu
  // de lire l'env, ou si elle transforme/normalise la valeur lue.
  it('AC12 : renvoie la valeur exacte de EXPO_PUBLIC_API_URL', () => {
    process.env.EXPO_PUBLIC_API_URL = 'https://api.test.local';
    expect(getApiUrl()).toBe('https://api.test.local');
  });

  // AC12 : une AUTRE valeur d'env donne une AUTRE sortie (prouve que la valeur est
  // bien LUE dynamiquement, pas figee). Falsifiable : une URL en dur ferait passer
  // le test precedent par coincidence mais rougirait ici.
  it('AC12 : suit la valeur de l env (staging local distincte)', () => {
    process.env.EXPO_PUBLIC_API_URL = 'http://192.168.1.42:8080';
    expect(getApiUrl()).toBe('http://192.168.1.42:8080');
  });

  // AC12 : env NON definie -> comportement spec (chaine vide, PAS d'URL en dur).
  // Falsifiable : echoue si getApiUrl retombe sur une URL backend en dur, ou si
  // elle renvoie undefined (la spec §3.3/D-BACKEND-URL exclut toute URL hardcodee).
  it('AC12 : EXPO_PUBLIC_API_URL non definie -> chaine vide (jamais d URL en dur)', () => {
    delete process.env.EXPO_PUBLIC_API_URL;
    const url = getApiUrl();
    expect(url).toBe('');
    expect(url).not.toMatch(/fly\.dev/);
    expect(url).not.toMatch(/coherence-metz\.fr/);
  });
});
