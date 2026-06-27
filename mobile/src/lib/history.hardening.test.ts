import {
  ALLOWED_RECORD_KEYS,
  HISTORY_CAP,
  HISTORY_SCHEMA_VERSION,
  HistoryRecord,
  HistoryStore,
  TITLE_MAX_LENGTH,
  buildRecord,
  clearAnalyses,
  deriveTitle,
  listAnalyses,
  normalizeUrlKey,
  parseRecords,
  removeAnalysis,
  saveAnalysis,
  upsertRecord,
} from './history';
import { ApiResult } from './types';

// =====================================================================
// PHASE B — durcissement adversarial (TESTEUR). SPEC mobile-tranche-b-historique.
//
// Objectif : ne PAS re-verifier le vert, mais chercher les FAUX-VERTS et trous
// de couverture. Chaque test ajoute ici est FALSIFIABLE (il rougit sur une
// regression realiste) et reste vert si le code respecte la spec.
//
// Lecons appliquees (.claude/lessons.md) :
//  - "absence d un champ par un test qui detecte REELLEMENT la presence"
//    (cross-agence-inc2b) -> on inspecte la SORTIE STOCKEE reelle du store.
//  - inertie/whitelist a CHAQUE niveau atteignable, pas seulement la racine
//    (contexte-local-v2 : invariant sur CHAQUE valeur, pas le chemin par defaut).
//  - rejects.toThrow() NU = faux-vert -> on contraint le MESSAGE et on interdit
//    le message de stub.
//  - bornes aux valeurs EXACTES (9.7).
//  - isolation d etat entre tests -> store recree en beforeEach.
// =====================================================================

function makeResult(score = 50): ApiResult {
  return {
    global_score: score,
    verdict: 'Coherence moyenne',
    confidence: 'Moyenne',
    pillars: [
      {
        label: 'Prix',
        verdict: 'Dans le marche',
        explanation: 'Aligne.',
        points: 18,
        max: 25,
      },
    ],
    actions: { highlights: ['x'], questions: ['q ?'], negotiation: ['n'] },
    local_context: {
      district: 'Sablon',
      summary: 'Quartier residentiel.',
      facts: [{ label: 'Gare', value: 'A 800 m', mode: 'WALK', estimated: false }],
      // claims[].text est une cle LEGITIME (notre agregat), JAMAIS interdite.
      claims: [
        { text: 'Proche gare', type: 'transport', status: 'coherent', note: 'OK' },
      ],
      precision: 'quartier',
    },
  };
}

class InMemoryStore implements HistoryStore {
  records: HistoryRecord[] = [];
  async read(): Promise<HistoryRecord[]> {
    return this.records.map((r) => ({ ...r }));
  }
  async write(records: HistoryRecord[]): Promise<void> {
    this.records = records.map((r) => ({ ...r }));
  }
  // Serialisation REELLE de ce qui a ete persiste (ce que l adaptateur sqlite
  // ecrirait dans result_json). C est la SORTIE STOCKEE, pas l entree.
  serialized(): string {
    return JSON.stringify(this.records);
  }
}

let store: InMemoryStore;
beforeEach(() => {
  store = new InMemoryStore();
});

// =====================================================================
// AXE 1 (le plus critique) — Invariant §11.3 : robustesse de la whitelist en
// PROFONDEUR. La SPEC §4.1 dit "jamais presents, a AUCUN NIVEAU de l
// enregistrement" pour raw_text/text/image_urls/photos/body. On prouve l
// absence dans la SORTIE STOCKEE reelle (le store), pas seulement a la racine.
//
// Distinction cle interdite vs sous-chaine : claims[].text est LEGITIME.
// =====================================================================
describe('AXE1 — whitelist en profondeur (sortie stockee reelle)', () => {
  // Detecteur de cle JSON (pas de sous-chaine) : on cherche la cle "<nom>" :
  function hasJsonKey(serialized: string, key: string): boolean {
    // matche une cle d objet JSON : "key": (apres { ou ,) — distingue d une
    // valeur de chaine. Ex. {"raw_text": -> match ; {"text":"..."} de claims
    // est volontairement EXCLU du set interdit (cle legitime).
    return new RegExp(`"${key}"\\s*:`).test(serialized);
  }

  it('AXE1 (sanity) : un result PROPRE produit une sortie stockee sans aucune cle interdite, MAIS conserve claims[].text', async () => {
    await saveAnalysis(store, {
      url: 'https://lbc.fr/ad/clean',
      title: 'Propre',
      result: makeResult(),
      savedAt: 1_700_000_000_000,
    });
    const out = store.serialized();
    for (const forbidden of ['raw_text', 'image_urls', 'photos', 'body']) {
      expect(hasJsonKey(out, forbidden)).toBe(false);
    }
    // claims[].text LEGITIME est bien conserve (sinon on aurait casse le rendu).
    expect(out).toContain('Proche gare');
    expect(hasJsonKey(out, 'text')).toBe(true); // claims[].text est presente et LEGITIME
  });

  it('AXE1 (CRITIQUE) : un champ interdit IMBRIQUE (result.local_context.raw_text/image_urls) ne doit JAMAIS finir dans la sortie stockee', async () => {
    const polluted = makeResult();
    // Injection en PROFONDEUR (et non a la racine) : c est exactement la forme
    // qu un DOM/scrape pourrait pousser par megarde dans local_context.
    (polluted.local_context as unknown as Record<string, unknown>).raw_text =
      'TEXTE BRUT DE L ANNONCE A NE JAMAIS STOCKER';
    (polluted.local_context as unknown as Record<string, unknown>).image_urls = [
      'https://img.leboncoin.fr/secret.jpg?rule=ad-large',
    ];

    // Le contrat (SPEC §4.1 + AC2) : soit buildRecord/saveAnalysis LEVE une
    // erreur nommee, soit la sortie stockee est expurgee. Dans les DEUX cas, la
    // cle interdite ne doit PAS apparaitre dans ce qui est persiste.
    let threw = false;
    try {
      await saveAnalysis(store, {
        url: 'https://lbc.fr/ad/deep',
        title: 'Imbrique',
        result: polluted,
        savedAt: 1_700_000_000_000,
      });
    } catch (err) {
      threw = true;
      expect((err as Error).message).toMatch(/raw_text|image_urls|photos|text|body/);
    }

    const out = store.serialized();
    // Preuve par la SORTIE STOCKEE : aucune cle interdite, a aucune profondeur.
    expect(hasJsonKey(out, 'raw_text')).toBe(false);
    expect(hasJsonKey(out, 'image_urls')).toBe(false);
    // Si rien n a ete leve, alors une entree a ete persistee : elle doit etre
    // expurgee (et non vide a cause d un crash silencieux).
    if (!threw) {
      expect(store.records.length).toBe(1);
    }
  });

  it('AXE1 (CRITIQUE, variante photos/body profonds) : photos/body imbriques ne fuient pas dans la sortie stockee', async () => {
    const polluted = makeResult();
    (polluted.local_context as unknown as Record<string, unknown>).photos = [
      'https://img/secret1.jpg',
    ];
    (polluted as unknown as Record<string, unknown>).body =
      'corps brut a ne pas stocker';

    try {
      await saveAnalysis(store, {
        url: 'https://lbc.fr/ad/deep2',
        title: 'Photos profondes',
        result: polluted,
        savedAt: 1_700_000_000_000,
      });
    } catch (err) {
      expect((err as Error).message).toMatch(/raw_text|image_urls|photos|text|body/);
    }
    const out = store.serialized();
    expect(hasJsonKey(out, 'photos')).toBe(false);
    expect(hasJsonKey(out, 'body')).toBe(false);
  });

  it('AXE1 (falsifiabilite) : la sonde DETECTE bien une cle interdite si elle est presente (anti faux-vert)', () => {
    // Auto-test du detecteur : prouve qu il rougirait si une cle interdite
    // fuyait reellement (sinon AXE1 serait un vert de complaisance).
    const leaked = JSON.stringify({
      schemaVersion: 1,
      result: { local_context: { raw_text: 'fuite' } },
    });
    expect(/"raw_text"\s*:/.test(leaked)).toBe(true);
    // et NE confond PAS une cle legitime text avec une valeur contenant "raw_text"
    const onlyValue = JSON.stringify({ note: 'mentionne raw_text en valeur' });
    expect(/"raw_text"\s*:/.test(onlyValue)).toBe(false);
  });
});

// =====================================================================
// AXE 2 — parseRecords defensif (trous au-dela de AC10).
// =====================================================================
describe('AXE2 — parseRecords defensif (durcissement)', () => {
  function validRaw(url = 'https://lbc.fr/ad/ok'): unknown {
    return buildRecord({
      url,
      title: 'Valide',
      result: makeResult(),
      savedAt: 1_700_000_000_000,
    });
  }

  it('AXE2 : cle interdite IMBRIQUEE dans result ne doit pas etre acceptee par parseRecords', () => {
    const withDeepForbidden = {
      ...(validRaw() as Record<string, unknown>),
      result: {
        ...makeResult(),
        local_context: {
          district: 'd',
          summary: 's',
          facts: [],
          raw_text: 'CONTENU INTERDIT IMBRIQUE',
        },
      },
    };
    const out = parseRecords([withDeepForbidden]);
    // Soit l entree est rejetee, soit elle est conservee mais expurgee : dans
    // les deux cas, raw_text ne doit pas survivre dans la sortie serialisee.
    expect(JSON.stringify(out)).not.toMatch(/"raw_text"\s*:/);
  });

  it('AXE2 : tableau mixte (valides + corrompues variees) -> ne garde QUE les valides, ordre preserve', () => {
    const a = validRaw('https://lbc.fr/ad/a');
    const b = validRaw('https://lbc.fr/ad/b');
    const out = parseRecords([
      a,
      null,
      { schemaVersion: 1 }, // incomplet
      'casse',
      [],
      { ...(a as Record<string, unknown>), schemaVersion: '1' }, // version string
      b,
    ]);
    expect(out).toHaveLength(2);
    expect(out.map((r) => r.url)).toEqual([
      'https://lbc.fr/ad/a',
      'https://lbc.fr/ad/b',
    ]);
  });

  it('AXE2 : schemaVersion float / 0 / 2 -> rejete (egalite stricte a 1)', () => {
    for (const v of [1.0001, 0, 2, -1, NaN]) {
      const rec = { ...(validRaw() as Record<string, unknown>), schemaVersion: v };
      expect(parseRecords([rec])).toEqual([]);
    }
    // borne exacte : schemaVersion === HISTORY_SCHEMA_VERSION accepte.
    const okRec = {
      ...(validRaw() as Record<string, unknown>),
      schemaVersion: HISTORY_SCHEMA_VERSION,
    };
    expect(parseRecords([okRec])).toHaveLength(1);
  });

  it('AXE2 : result manquant ou null -> entree rejetee', () => {
    const noResult = { ...(validRaw() as Record<string, unknown>) };
    delete (noResult as Record<string, unknown>).result;
    expect(parseRecords([noResult])).toEqual([]);

    const nullResult = { ...(validRaw() as Record<string, unknown>), result: null };
    expect(parseRecords([nullResult])).toEqual([]);
  });

  it('AXE2 : objet non-tableau au top -> [] (jamais d iteration sur les cles d objet)', () => {
    expect(parseRecords({ 0: validRaw(), length: 1 })).toEqual([]);
  });

  it('AXE2 : une valide n est JAMAIS perdue a cause d une voisine corrompue', () => {
    const good = validRaw('https://lbc.fr/ad/survivor');
    const out = parseRecords([{ junk: true }, good, undefined, NaN]);
    expect(out).toHaveLength(1);
    expect(out[0].url).toBe('https://lbc.fr/ad/survivor');
  });
});

// =====================================================================
// AXE 3 — Dedup + plafond en interaction (au-dela de AC3/AC5).
// =====================================================================
describe('AXE3 — dedup x plafond', () => {
  function fill50(): HistoryRecord[] {
    let list: HistoryRecord[] = [];
    for (let i = 0; i < HISTORY_CAP; i++) {
      list = upsertRecord(
        list,
        buildRecord({
          url: `https://lbc.fr/ad/${i}`,
          title: `t${i}`,
          result: makeResult(i),
          savedAt: 1000 + i,
        }),
      );
    }
    return list;
  }

  it('AXE3 (CRITIQUE) : upsert d une URL EXISTANTE a 50 entrees -> reste 50, n evince RIEN a tort (dedup AVANT plafond)', () => {
    const list = fill50();
    expect(list).toHaveLength(50);
    // re-upsert de l URL la plus ancienne (ad/0) avec savedAt le plus recent.
    const next = upsertRecord(
      list,
      buildRecord({
        url: 'https://lbc.fr/ad/0?utm=z',
        title: 'maj',
        result: makeResult(),
        savedAt: 999999,
      }),
    );
    expect(next).toHaveLength(50);
    // ad/0 toujours present (mis a jour, remonte en tete), aucune autre evincee.
    expect(next[0].title).toBe('maj');
    const keys = new Set(next.map((r) => normalizeUrlKey(r.url)));
    for (let i = 0; i < 50; i++) {
      expect(keys.has(normalizeUrlKey(`https://lbc.fr/ad/${i}`))).toBe(true);
    }
  });

  it('AXE3 : URLs differant SEULEMENT par query/fragment/casse de host -> meme cle (une seule entree)', () => {
    const variants = [
      'https://lbc.fr/ad/777',
      'https://lbc.fr/ad/777?utm=a',
      'https://lbc.fr/ad/777#gallery',
      'https://LBC.FR/ad/777?x=1#y',
    ];
    let list: HistoryRecord[] = [];
    variants.forEach((url, i) => {
      list = upsertRecord(
        list,
        buildRecord({ url, title: `v${i}`, result: makeResult(), savedAt: 1000 + i }),
      );
    });
    expect(list).toHaveLength(1);
    expect(list[0].title).toBe('v3'); // dernier upsert gagne
  });

  it('AXE3 : deux URLs NON parsables DIFFERENTES restent distinctes (repli sans crash)', () => {
    let list: HistoryRecord[] = [];
    list = upsertRecord(
      list,
      buildRecord({ url: 'pas une url A', title: 'A', result: makeResult(), savedAt: 1 }),
    );
    list = upsertRecord(
      list,
      buildRecord({ url: 'pas une url B', title: 'B', result: makeResult(), savedAt: 2 }),
    );
    expect(list).toHaveLength(2);
    // meme URL non parsable -> meme cle (pas de doublon).
    list = upsertRecord(
      list,
      buildRecord({ url: 'pas une url A', title: 'A2', result: makeResult(), savedAt: 3 }),
    );
    expect(list).toHaveLength(2);
    expect(list[0].title).toBe('A2');
  });
});

// =====================================================================
// AXE 4 — deriveTitle : Unicode / CRLF / lignes d espaces / borne exacte.
// =====================================================================
describe('AXE4 — deriveTitle robustesse', () => {
  it('AXE4 : CRLF -> \\r retire de la 1re ligne (pas de caractere de controle dans le titre)', () => {
    const out = deriveTitle('Appartement T3\r\nDescription suite');
    expect(out).toBe('Appartement T3');
    expect(out).not.toMatch(/[\r\n]/);
  });

  it('AXE4 : lignes faites uniquement d espaces/tabs avant une vraie ligne -> on saute jusqu a la 1re ligne non vide', () => {
    const out = deriveTitle('   \n\t  \n   Vrai titre   \nreste');
    expect(out).toBe('Vrai titre');
  });

  it('AXE4 : 1re ligne d espaces multiples internes -> conserves apres trim de bord', () => {
    expect(deriveTitle('  Maison   4   pieces  ')).toBe('Maison   4   pieces');
  });

  it('AXE4 (borne exacte multi-octets) : emoji a la limite 80 -> longueur <= 80, jamais d exception', () => {
    // 'a' + 40 emoji = 1 + 80 unites = 81 unites ; slice(0,80) selon spec (80
    // PREMIERS caracteres = unites JS). On verifie juste : pas d exception,
    // longueur exactement TITLE_MAX_LENGTH, et titre non vide.
    const s = 'a' + '\u{1F600}'.repeat(40);
    let out = '';
    expect(() => {
      out = deriveTitle(s);
    }).not.toThrow();
    expect(out.length).toBe(TITLE_MAX_LENGTH);
    expect(out.length).toBeGreaterThan(0);
  });

  it('AXE4 (borne exacte) : ligne de 80 contenant des accents -> inchangee (80)', () => {
    const line = 'e' + 'é'.repeat(79); // 80 code units (é = 1 unite en JS BMP)
    expect(line.length).toBe(80);
    expect(deriveTitle(line)).toBe(line);
  });

  it('AXE4 : whitespace-only multi-ligne -> repli (jamais chaine vide)', () => {
    const out = deriveTitle('   \n\t\n  \r\n   ');
    expect(out).toBe('Analyse sans titre');
    expect(out.length).toBeGreaterThan(0);
  });
});

// =====================================================================
// AXE 5 — AC11 propagation d erreur : nature + write rejette APRES buildRecord.
// =====================================================================
describe('AXE5 — propagation d erreur (nature, pas throw nu)', () => {
  it('AXE5 : write() rejette APRES un buildRecord valide -> l erreur d ECRITURE remonte (pas avalee, pas le message de stub)', async () => {
    let readCalled = false;
    let writeAttempted = false;
    const failingWrite: HistoryStore = {
      async read() {
        readCalled = true;
        return [];
      },
      async write() {
        writeAttempted = true;
        throw new Error('DISK_FULL_42');
      },
    };
    const p = saveAnalysis(failingWrite, {
      url: 'https://lbc.fr/ad/wr',
      title: 'T',
      result: makeResult(), // buildRecord VALIDE : on atteint bien le write
      savedAt: 1_700_000_000_000,
    });
    // la NATURE : message d ecriture, et la cause sous-jacente preservee.
    await expect(p).rejects.toThrow(/write|store|sqlite/i);
    await expect(
      saveAnalysis(failingWrite, {
        url: 'https://lbc.fr/ad/wr',
        title: 'T',
        result: makeResult(),
        savedAt: 1_700_000_000_000,
      }),
    ).rejects.toThrow(/DISK_FULL_42/);
    expect(readCalled).toBe(true);
    expect(writeAttempted).toBe(true);
  });

  it('AXE5 : removeAnalysis avec read() en echec -> rejette avec nature lecture', async () => {
    const failingRead: HistoryStore = {
      async read() {
        throw new Error('SQLITE_BUSY_99');
      },
      async write() {
        /* noop */
      },
    };
    await expect(removeAnalysis(failingRead, 'x')).rejects.toThrow(
      /read|store|sqlite/i,
    );
    await expect(removeAnalysis(failingRead, 'x')).rejects.toThrow(/SQLITE_BUSY_99/);
  });

  it('AXE5 : clearAnalyses avec write() en echec -> rejette avec nature ecriture', async () => {
    const failingWrite: HistoryStore = {
      async read() {
        return [];
      },
      async write() {
        throw new Error('WRITE_BOOM');
      },
    };
    await expect(clearAnalyses(failingWrite)).rejects.toThrow(/write|store|sqlite/i);
    await expect(clearAnalyses(failingWrite)).rejects.toThrow(/WRITE_BOOM/);
  });

  it('AXE5 (contraste) : un buildRecord avec result interdit a la RACINE leve AVANT tout write (write jamais tente)', async () => {
    let writeAttempted = false;
    const watchWrite: HistoryStore = {
      async read() {
        return [];
      },
      async write() {
        writeAttempted = true;
      },
    };
    const polluted = {
      ...makeResult(),
      raw_text: 'INTERDIT RACINE',
    } as unknown as ApiResult;
    await expect(
      saveAnalysis(watchWrite, {
        url: 'https://lbc.fr/ad/x',
        title: 'T',
        result: polluted,
        savedAt: 1,
      }),
    ).rejects.toThrow(/raw_text/);
    // le rejet a court-circuite l ecriture : rien de pollue n a pu etre persiste.
    expect(writeAttempted).toBe(false);
  });
});

// =====================================================================
// AXE 6 — Isolation / etat de module (pas de cache global dans history.ts).
// =====================================================================
describe('AXE6 — pas d etat de module global', () => {
  it('AXE6 (1/2) : ecrit dans un store local', async () => {
    await saveAnalysis(store, {
      url: 'https://lbc.fr/ad/iso',
      title: 'T',
      result: makeResult(),
      savedAt: 1,
    });
    expect(await listAnalyses(store)).toHaveLength(1);
  });

  it('AXE6 (2/2) : un NOUVEAU store independant ne voit rien du precedent (aucun cache module)', async () => {
    const other = new InMemoryStore();
    expect(await listAnalyses(other)).toEqual([]);
    // et le store du beforeEach est neuf aussi.
    expect(await listAnalyses(store)).toEqual([]);
  });

  it('AXE6 : statique — history.ts ne porte aucun etat de module mutable (let/var de haut niveau hors const)', () => {
    const fs = require('fs') as typeof import('fs');
    const path = require('path') as typeof import('path');
    const source = fs.readFileSync(path.join(__dirname, 'history.ts'), 'utf8');
    // pas de cache/buckets/store global au niveau module (pattern des lecons
    // photo_evidence/_CACHE, rate_limit/_buckets cote backend).
    expect(source).not.toMatch(/^\s*(let|var)\s+_?(cache|store|buckets|state)\b/im);
  });
});

// =====================================================================
// AXE 7 (B1) — `text` interdit a TOUTE profondeur SAUF claims[].text (§4.1).
// La derogation est POSITIVE (whitelist de chemin, lecon 9.10 "whitelist
// positive, jamais blacklist de position") : `text` n'est tolere que comme
// propriete directe d'un element du tableau `claims`. Partout ailleurs (racine,
// local_context.text, sous tout autre objet/tableau) il est interdit au meme
// titre que raw_text/image_urls/photos/body.
//
// Falsifiabilite : ces tests ROUGISSENT sur un controle de `text` limite a la
// racine (l'ancien FORBIDDEN_KEY_RESULT_ROOT), car ils injectent `text` EN
// PROFONDEUR hors claims, et prouvent l'absence par la SORTIE STOCKEE reelle.
// =====================================================================
describe('AXE7 (B1) — `text` interdit en profondeur sauf claims[].text', () => {
  function hasJsonKey(serialized: string, key: string): boolean {
    return new RegExp(`"${key}"\\s*:`).test(serialized);
  }

  it('AXE7 (CRITIQUE) : result.local_context.text IMBRIQUE -> jamais persiste (buildRecord leve, OU sortie stockee expurgee)', async () => {
    const polluted = makeResult();
    // `text` brut d'annonce pousse en PROFONDEUR (hors claims) : c'est le defaut B1.
    (polluted.local_context as unknown as Record<string, unknown>).text =
      'TEXTE BRUT DE L ANNONCE A NE JAMAIS STOCKER';

    let threw = false;
    try {
      await saveAnalysis(store, {
        url: 'https://lbc.fr/ad/deep-text',
        title: 'Text imbrique',
        result: polluted,
        savedAt: 1_700_000_000_000,
      });
    } catch (err) {
      threw = true;
      expect((err as Error).message).toMatch(/text/);
    }

    const out = store.serialized();
    // local_context.text brut ne doit JAMAIS finir dans la sortie stockee.
    expect(out).not.toContain('TEXTE BRUT DE L ANNONCE A NE JAMAIS STOCKER');
    if (!threw) {
      // s'il n'a pas leve, l'entree persistee doit etre expurgee, pas un crash.
      expect(store.records.length).toBe(1);
      expect(hasJsonKey(store.serialized(), 'text')).toBe(false);
    }
  });

  it('AXE7 (buildRecord) : local_context.text imbrique -> ForbiddenFieldError nommee contenant "text"', () => {
    const polluted = makeResult();
    (polluted.local_context as unknown as Record<string, unknown>).text =
      'BRUT';
    expect(() =>
      buildRecord({
        url: 'https://lbc.fr/ad/x',
        title: 'T',
        result: polluted,
        savedAt: 1,
      }),
    ).toThrow(/text/);
  });

  it('AXE7 : `text` sous un objet QUELCONQUE hors claims (pillars[].text) -> interdit', () => {
    const polluted = makeResult();
    (polluted.pillars[0] as unknown as Record<string, unknown>).text =
      'BRUT DANS PILLAR';
    expect(() =>
      buildRecord({
        url: 'https://lbc.fr/ad/pillar-text',
        title: 'T',
        result: polluted,
        savedAt: 1,
      }),
    ).toThrow(/text/);
  });

  it('AXE7 : `text` sous claims[].something (objet imbrique plus profond) -> interdit (pas claims[].text direct)', () => {
    const polluted = makeResult();
    const claim = (polluted.local_context as unknown as Record<string, unknown>)
      .claims as unknown as Array<Record<string, unknown>>;
    claim[0].nested = { text: 'BRUT IMBRIQUE SOUS UN CLAIM' };
    expect(() =>
      buildRecord({
        url: 'https://lbc.fr/ad/nested-claim-text',
        title: 'T',
        result: polluted,
        savedAt: 1,
      }),
    ).toThrow(/text/);
  });

  it('AXE7 (parseRecords) : entree empoisonnee par local_context.text -> rejetee, jamais rechargee', () => {
    const poisoned = {
      schemaVersion: HISTORY_SCHEMA_VERSION,
      id: 'https://lbc.fr/ad/poison',
      url: 'https://lbc.fr/ad/poison',
      title: 'Poison',
      savedAt: 1_700_000_000_000,
      result: {
        ...makeResult(),
        local_context: {
          district: 'd',
          summary: 's',
          facts: [],
          text: 'BRUT EMPOISONNE A NE PAS RECHARGER',
        },
      },
    };
    const out = parseRecords([poisoned]);
    expect(out).toEqual([]);
    expect(JSON.stringify(out)).not.toContain('BRUT EMPOISONNE A NE PAS RECHARGER');
  });

  it('AXE7 (contraste / sanity) : claims[].text LEGITIME est conserve (deperdition nulle du cas propre)', async () => {
    await saveAnalysis(store, {
      url: 'https://lbc.fr/ad/clean-text',
      title: 'Propre',
      result: makeResult(),
      savedAt: 1_700_000_000_000,
    });
    expect(store.records).toHaveLength(1);
    const out = store.serialized();
    // claims[].text "Proche gare" toujours present (cle text legitime).
    expect(out).toContain('Proche gare');
    expect(hasJsonKey(out, 'text')).toBe(true);
    // et le result recharge reste deep-equal a l'origine (AC1 / AXE1 sanity).
    const list = await listAnalyses(store);
    expect(list[0].result).toEqual(makeResult());
  });
});

// =====================================================================
// AXE 8 (N1) — Tri stable a savedAt EGAL : l'entree fraichement upsertee passe
// en TETE (§5.1). Falsifiabilite : ROUGIT sur un push + sort stable (l'ancienne
// resterait en index 0).
// =====================================================================
describe('AXE8 (N1) — savedAt egal : upserte en tete', () => {
  it('AXE8 : deux URLs distinctes, MEME savedAt -> la derniere upsertee est en index 0', () => {
    const t = 1_700_000_000_000;
    let list: HistoryRecord[] = [];
    list = upsertRecord(
      list,
      buildRecord({ url: 'https://lbc.fr/ad/old', title: 'OLD', result: makeResult(), savedAt: t }),
    );
    list = upsertRecord(
      list,
      buildRecord({ url: 'https://lbc.fr/ad/new', title: 'NEW', result: makeResult(), savedAt: t }),
    );
    expect(list).toHaveLength(2);
    expect(list[0].title).toBe('NEW');
    expect(list[1].title).toBe('OLD');
  });

  it('AXE8 : re-upsert (dedup) a savedAt egal -> l entree mise a jour remonte en tete', () => {
    const t = 1_700_000_000_000;
    let list: HistoryRecord[] = [];
    list = upsertRecord(
      list,
      buildRecord({ url: 'https://lbc.fr/ad/a', title: 'A', result: makeResult(), savedAt: t }),
    );
    list = upsertRecord(
      list,
      buildRecord({ url: 'https://lbc.fr/ad/b', title: 'B', result: makeResult(), savedAt: t }),
    );
    // re-upsert de A au MEME savedAt -> A doit repasser devant B.
    list = upsertRecord(
      list,
      buildRecord({ url: 'https://lbc.fr/ad/a', title: 'A2', result: makeResult(), savedAt: t }),
    );
    expect(list).toHaveLength(2);
    expect(list[0].title).toBe('A2');
  });
});
