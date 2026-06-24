import { analyzeListing } from './analyzeApi';
import { ApiResult } from './types';

// =====================================================================
// PHASE A — tests-first (TESTEUR). SPEC mobile-phase2-tranche1 §5.A AC10 + AC11.
// Cible : src/lib/analyzeApi.ts (stub `throw NOT_IMPLEMENTED: analyzeListing`).
// ROUGES maintenant pour la BONNE raison (NOT_IMPLEMENTED) ; verts apres impl
// SANS reecriture.
//
// Lecons appliquees (.claude/lessons.md) :
//  - mobile-phase1-image-urls / cross-agence-inc2b : prouver le TRANSIT REEL — la
//    LISTE EXACTE postee, dans le MEME ORDRE — jamais "la requete part".
//  - 9.10 (avaler une erreur) : un non-ok doit REJETER, pas renvoyer un faux succes.
//
// fetch est mocke (global.fetch = jest.fn()) et RESTAURE en afterEach.
// EXPO_PUBLIC_API_URL est fixe a une valeur de test et restaure en afterEach.
// =====================================================================

const TEST_API_URL = 'https://api.test.local';

// ApiResult minimal renvoye par un fetch ok:true (assez pour prouver le passage).
const MINIMAL_RESULT: ApiResult = {
  global_score: 72,
  verdict: 'Coherence moyenne',
  confidence: 'Moyenne',
  pillars: [],
  actions: { questions: [], negotiation: [] },
};

const realFetch = global.fetch;
let savedApiUrl: string | undefined;

beforeEach(() => {
  savedApiUrl = process.env.EXPO_PUBLIC_API_URL;
  process.env.EXPO_PUBLIC_API_URL = TEST_API_URL;
});

afterEach(() => {
  global.fetch = realFetch;
  if (savedApiUrl === undefined) {
    delete process.env.EXPO_PUBLIC_API_URL;
  } else {
    process.env.EXPO_PUBLIC_API_URL = savedApiUrl;
  }
  jest.restoreAllMocks();
});

function mockFetchOk(result: ApiResult): jest.Mock {
  const fn = jest.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => result,
  });
  global.fetch = fn as unknown as typeof fetch;
  return fn;
}

describe('analyzeListing — AC10 : transit reel vers /analyze (liste EXACTE postee)', () => {
  // AC10 (keystone) : 2 URLs ad-large, fetch ok:true -> on asserte sur
  // fetch.mock.calls[0] : (a) URL EXACTE `${EXPO_PUBLIC_API_URL}/analyze` ;
  // (b) method POST ; (c) header Content-Type: application/json ; (d) body JSON
  // STRICTEMENT egal a { raw_text, image_urls:[les 2 URLs, MEME ORDRE] }.
  // C'est le TRANSIT de la LISTE EXACTE qui est prouve, pas "fetch appele".
  //
  // Falsifiabilite : si analyzeListing FILTRE ou REORDONNE les URLs avant l'envoi
  // (ex. .sort(), .reverse(), .filter(...)), le toEqual sur image_urls rougit ;
  // si l'URL appelee n'est pas `${EXPO_PUBLIC_API_URL}/analyze` (ex. URL en dur),
  // l'assert (a) rougit ; si la methode/header changent, (b)/(c) rougissent.
  it('AC10 : POST le body EXACT (raw_text + 2 URLs meme ordre) a la bonne URL', async () => {
    const fetchMock = mockFetchOk(MINIMAL_RESULT);
    const rawText = 'Appartement T3 lumineux, 65 m2, proche gare';
    const imageUrls = [
      'https://img.leboncoin.fr/x.jpg?rule=ad-large',
      'https://img.leboncoin.fr/y.jpg?rule=ad-large',
    ];

    await analyzeListing(rawText, imageUrls);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [calledUrl, init] = fetchMock.mock.calls[0];

    // (a) URL EXACTE
    expect(calledUrl).toBe(`${TEST_API_URL}/analyze`);
    // (b) methode
    expect(init.method).toBe('POST');
    // (c) en-tete Content-Type: application/json (insensible a la casse de la cle)
    const headers = init.headers as Record<string, string>;
    const contentType =
      headers['Content-Type'] ?? headers['content-type'];
    expect(contentType).toBe('application/json');
    // (d) body JSON strictement egal — LISTE EXACTE, MEME ORDRE
    const sentBody = JSON.parse(init.body as string);
    expect(sentBody).toEqual({
      raw_text: rawText,
      image_urls: [
        'https://img.leboncoin.fr/x.jpg?rule=ad-large',
        'https://img.leboncoin.fr/y.jpg?rule=ad-large',
      ],
    });
    // Garde supplementaire : ordre exact des 2 URLs (anti reorder silencieux).
    expect(sentBody.image_urls).toEqual(imageUrls);
  });

  // AC10 — preuve d'ordre renforcee : 3 URLs dont l'ordre alphabetique DIFFERE de
  // l'ordre d'entree -> le body conserve l'ordre d'ENTREE, pas un tri.
  // Falsifiable : un .sort() dans analyzeListing rougirait ici (mais pas forcement
  // sur le cas a 2 URLs deja triees).
  it('AC10 : 3 URLs en ordre non trie -> ordre d entree preserve dans le body', async () => {
    const fetchMock = mockFetchOk(MINIMAL_RESULT);
    const imageUrls = [
      'https://img.leboncoin.fr/zzz.jpg?rule=ad-large',
      'https://img.leboncoin.fr/aaa.jpg?rule=ad-large',
      'https://img.leboncoin.fr/mmm.jpg?rule=ad-large',
    ];

    await analyzeListing('texte', imageUrls);

    const sentBody = JSON.parse(fetchMock.mock.calls[0][1].body as string);
    expect(sentBody.image_urls).toEqual(imageUrls);
  });

  // AC10 / AC9 coherence : galerie VIDE -> le body s'appuie sur buildAnalyzeBody
  // qui OMET la cle image_urls (decision GATE 2 n3). On asserte l'absence de cle
  // image_urls ET l'absence TOTALE de cle 'url' dans le body REELLEMENT envoye.
  // Falsifiable : si analyzeListing posait image_urls:[] ou injectait url, rougit.
  it('AC10/AC9 : galerie vide -> body envoye SANS cle image_urls et JAMAIS de cle url', async () => {
    const fetchMock = mockFetchOk(MINIMAL_RESULT);

    await analyzeListing('texte seul', []);

    const sentBody = JSON.parse(fetchMock.mock.calls[0][1].body as string);
    expect(sentBody).toEqual({ raw_text: 'texte seul' });
    expect('image_urls' in sentBody).toBe(false);
    expect('url' in sentBody).toBe(false);
  });

  // AC10 : le retour ok:true est bien l'ApiResult parse (pas un objet vide/factice).
  // Prouve que analyzeListing REND le json du backend (lecon : pas de faux succes
  // dans l'autre sens non plus — le succes doit transiter la vraie reponse).
  it('AC10 : reponse ok:true -> renvoie l ApiResult parse du backend', async () => {
    mockFetchOk(MINIMAL_RESULT);

    const result = await analyzeListing('texte', [
      'https://img.leboncoin.fr/x.jpg?rule=ad-large',
    ]);

    expect(result).toEqual(MINIMAL_RESULT);
  });

  // AC10 : le body ne contient JAMAIS la cle 'url' meme avec une galerie non vide
  // (anti re-fetch serveur, SPEC §3.4). Assertion sur le body REELLEMENT poste.
  it('AC10 : galerie non vide -> body envoye ne contient JAMAIS la cle url', async () => {
    const fetchMock = mockFetchOk(MINIMAL_RESULT);

    await analyzeListing('texte', [
      'https://img.leboncoin.fr/x.jpg?rule=ad-large',
    ]);

    const sentBody = JSON.parse(fetchMock.mock.calls[0][1].body as string);
    expect('url' in sentBody).toBe(false);
  });
});

describe('analyzeListing — AC11 : /analyze non-ok -> rejet, pas de faux succes', () => {
  // AC11 (keystone) : fetch ok:false status:422 detail:"msg backend" -> rejette
  // avec un message CONTENANT "msg backend", et ne renvoie PAS un ApiResult.
  //
  // Falsifiabilite : si l'erreur est AVALEE (ex. analyzeListing renvoie un
  // ApiResult vide/factice ou la reponse non-ok sans throw), `rejects.toThrow`
  // rougit (la promesse resout au lieu de rejeter). Si le message du throw ne
  // reprend pas le detail backend, le matcher /msg backend/ rougit.
  it('AC11 : 422 avec detail -> rejette avec un message contenant le detail backend', async () => {
    const fetchMock = jest.fn().mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({ detail: 'msg backend' }),
    });
    global.fetch = fetchMock as unknown as typeof fetch;

    await expect(
      analyzeListing('texte', ['https://img.leboncoin.fr/x.jpg?rule=ad-large']),
    ).rejects.toThrow(/msg backend/);
  });

  // AC11 : non-ok SANS detail exploitable (json sans cle detail) -> rejet QUAND MEME,
  // avec un message qui SURFACE le code HTTP (500) faute de detail backend lisible.
  // Pas de faux succes meme si le backend ne fournit pas de detail lisible.
  //
  // IMPORTANT (anti faux-vert) : le matcher /500/ DISTINGUE le stub d'une vraie impl.
  // Un `rejects.toThrow()` NU serait VERT contre le stub (qui throw NOT_IMPLEMENTED)
  // -> faux-vert (la rejection ne prouverait pas le traitement du non-ok). On exige
  // donc le statut dans le message ET on interdit explicitement NOT_IMPLEMENTED.
  // Falsifiable : si analyzeListing ne throw que lorsque `detail` est present (json
  // = {} resoudrait), rouge ; si le statut n'est pas surface, rouge.
  it('AC11 : non-ok sans detail exploitable (json {}) -> rejette en surfacant le statut 500', async () => {
    const fetchMock = jest.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({}),
    });
    global.fetch = fetchMock as unknown as typeof fetch;

    await expect(analyzeListing('texte', [])).rejects.toThrow(/500/);
    await expect(analyzeListing('texte', [])).rejects.not.toThrow(
      /NOT_IMPLEMENTED/,
    );
  });

  // AC11 : non-ok dont le corps n'est meme pas du JSON (json() leve) -> rejet,
  // jamais un faux succes ni une exception NOT_IMPLEMENTED du stub.
  // Anti faux-vert : on exige le statut 502 dans le message (un `toThrow()` nu
  // passerait contre le stub). Falsifiable : un succes silencieux (resolution) ou
  // une rejection non liee au contrat (NOT_IMPLEMENTED) rougit.
  it('AC11 : non-ok dont le corps n est pas du JSON -> rejette en surfacant le statut 502', async () => {
    const fetchMock = jest.fn().mockResolvedValue({
      ok: false,
      status: 502,
      json: async () => {
        throw new Error('corps non JSON');
      },
    });
    global.fetch = fetchMock as unknown as typeof fetch;

    await expect(analyzeListing('texte', [])).rejects.toThrow(/502/);
    await expect(analyzeListing('texte', [])).rejects.not.toThrow(
      /NOT_IMPLEMENTED/,
    );
  });
});
