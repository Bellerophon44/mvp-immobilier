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
import { analyzeListing } from './analyzeApi';
import { ApiResult } from './types';

// =====================================================================
// PHASE A — tests-first (TESTEUR). SPEC mobile-tranche-b-historique §7.A AC1..AC14.
// Cible : src/lib/history.ts (stub minimal). ROUGES maintenant pour la BONNE
// raison (logique absente), VERTS apres impl SANS reecriture des tests.
//
// Lecons appliquees (.claude/lessons.md) :
//  - rejects.toThrow() NU = faux-vert -> AC11 asserte la NATURE du message
//    (/read|store|sqlite/i, /write|store|sqlite/i) ET interdit un message de stub.
//  - bornes aux valeurs EXACTES (9.7) -> AC5 teste 50 ET 51, AC7 teste 79/80/81.
//  - inertie prouvee sur la dependance TERMINALE + contraste (mobile-phase1) ->
//    AC13 observe global.fetch (call_count===0) ET prouve par contraste que
//    analyzeListing, lui, l'incremente.
//  - isolation d'etat entre tests (9.7/9.9) -> store in-memory reinitialise en
//    beforeEach ; AC14 prouve l'absence de fuite.
//  - whitelist : prouver l'ABSENCE d'un champ interdit par un test qui detecte
//    REELLEMENT sa presence (cross-agence-inc2b) -> AC2.
// =====================================================================

// ApiResult VALIDE construit a partir du VRAI type de types.ts (jamais invente).
function makeResult(score = 72): ApiResult {
  return {
    global_score: score,
    verdict: 'Coherence moyenne',
    confidence: 'Moyenne',
    pillars: [
      {
        label: 'Prix',
        verdict: 'Dans le marche',
        explanation: 'Aligne sur le quartier.',
        points: 18,
        max: 25,
        scope: 'quartier',
        scope_name: 'Sablon',
        dpe_band: 'D',
        n_comparables: 12,
        refinable: false,
        listing_price_m2: 2900,
      },
    ],
    actions: {
      highlights: ['Bien lumineux'],
      questions: ['Montant des charges ?'],
      negotiation: ['Travaux toiture'],
    },
    local_context: {
      district: 'Sablon',
      summary: 'Quartier residentiel.',
      facts: [{ label: 'Gare', value: 'A 800 m', mode: 'WALK', estimated: false }],
      claims: [
        { text: 'Proche gare', type: 'transport', status: 'coherent', note: 'OK' },
      ],
      precision: 'quartier',
    },
  };
}

// -----------------------------------------------------------------
// Store in-memory de test implementant HistoryStore. Reinitialise en beforeEach.
// AUCUN etat de module ne fuit (l'instance est recreee a chaque test).
// -----------------------------------------------------------------
class InMemoryStore implements HistoryStore {
  private records: HistoryRecord[] = [];

  async read(): Promise<HistoryRecord[]> {
    // Copie defensive : la logique pure ne doit pas muter l'etat interne du store.
    return this.records.map((r) => ({ ...r }));
  }

  async write(records: HistoryRecord[]): Promise<void> {
    this.records = records.map((r) => ({ ...r }));
  }

  // Helper de test (hors interface) pour pre-seeder l'etat.
  _seed(records: HistoryRecord[]): void {
    this.records = records.map((r) => ({ ...r }));
  }

  _size(): number {
    return this.records.length;
  }
}

// Store qui ECHOUE en lecture (AC11).
class FailingReadStore implements HistoryStore {
  async read(): Promise<HistoryRecord[]> {
    throw new Error('SQLITE_READ_FAILED');
  }
  async write(_records: HistoryRecord[]): Promise<void> {
    // pas atteint pour le cas read
  }
}

// Store qui lit normalement mais ECHOUE en ecriture (AC11).
class FailingWriteStore implements HistoryStore {
  async read(): Promise<HistoryRecord[]> {
    return [];
  }
  async write(_records: HistoryRecord[]): Promise<void> {
    throw new Error('SQLITE_WRITE_FAILED');
  }
}

let store: InMemoryStore;

beforeEach(() => {
  store = new InMemoryStore();
});

// =====================================================================
// AC1 — Persistance via la facade : saveAnalysis ajoute un enregistrement complet.
// =====================================================================
describe('AC1 — saveAnalysis ajoute un enregistrement complet', () => {
  it('AC1 : store vide -> 1 entree, champs preserves, schemaVersion=1, result deep-equal', async () => {
    const result = makeResult();
    const savedAt = 1_700_000_000_000;
    await saveAnalysis(store, {
      url: 'https://lbc.fr/ad/123',
      title: 'Appartement T3 Metz',
      result,
      savedAt,
    });

    const list = await listAnalyses(store);
    expect(list).toHaveLength(1);
    const rec = list[0];
    expect(rec.url).toBe('https://lbc.fr/ad/123');
    expect(rec.title).toBe('Appartement T3 Metz');
    expect(rec.savedAt).toBe(savedAt);
    expect(rec.schemaVersion).toBe(HISTORY_SCHEMA_VERSION);
    expect(rec.schemaVersion).toBe(1);
    // result strictement egal (deep-equal) — aucun champ perdu/altere.
    expect(rec.result).toEqual(result);
  });
});

// =====================================================================
// AC2 — Whitelist stricte (statique + dynamique falsifiable).
// =====================================================================
describe('AC2 — whitelist stricte, statique + dynamique falsifiable', () => {
  it('AC2 (statique) : ALLOWED_RECORD_KEYS == exactement le set autorise, sans cle interdite', () => {
    expect(new Set(ALLOWED_RECORD_KEYS)).toEqual(
      new Set(['schemaVersion', 'id', 'url', 'title', 'savedAt', 'result']),
    );
    for (const forbidden of ['raw_text', 'text', 'image_urls', 'photos', 'body']) {
      expect(ALLOWED_RECORD_KEYS).not.toContain(forbidden);
    }
  });

  it('AC2 (statique) : buildRecord ne produit AUCUNE cle hors whitelist', () => {
    const rec = buildRecord({
      url: 'https://lbc.fr/ad/1',
      title: 'T2',
      result: makeResult(),
      savedAt: 1_700_000_000_000,
    });
    expect(new Set(Object.keys(rec))).toEqual(new Set(ALLOWED_RECORD_KEYS));
  });

  it('AC2 (dynamique falsifiable) : un result avec champ interdit -> erreur NOMMEE OU serialisation sans la cle interdite', () => {
    // result augmente de champs INTERDITS (raw_text + image_urls).
    const polluted = {
      ...makeResult(),
      raw_text: 'TEXTE BRUT DE L ANNONCE A NE JAMAIS STOCKER',
      image_urls: ['https://img.leboncoin.fr/secret.jpg?rule=ad-large'],
    } as unknown as ApiResult;

    const forbiddenInSerialization = /"(raw_text|image_urls|photos|text)"/;

    let threwNamed = false;
    let rec: HistoryRecord | undefined;
    try {
      rec = buildRecord({
        url: 'https://lbc.fr/ad/2',
        title: 'T3',
        result: polluted,
        savedAt: 1_700_000_000_000,
      });
    } catch (err) {
      // Branche "erreur nommee" : le message DOIT identifier le champ interdit.
      threwNamed = true;
      expect((err as Error).message).toMatch(
        /raw_text|image_urls|photos|text/,
      );
    }

    if (!threwNamed) {
      // Branche "serialisation expurgee" : la cle interdite n'apparait A AUCUNE
      // profondeur. Ce test ROUGIT si la whitelist est retiree (la cle fuiterait).
      expect(rec).toBeDefined();
      expect(JSON.stringify(rec)).not.toMatch(forbiddenInSerialization);
    }
  });

  it('AC2 (falsifiabilite) : la serialisation d un enregistrement issu de saveAnalysis ne contient jamais raw_text/image_urls/photos/text', async () => {
    const polluted = {
      ...makeResult(),
      raw_text: 'NE PAS STOCKER',
      photos: ['x'],
      text: 'NE PAS STOCKER NON PLUS',
    } as unknown as ApiResult;

    // saveAnalysis peut rejeter (erreur nommee) OU produire un enregistrement
    // expurge ; dans les deux cas, AUCUN champ interdit ne doit etre persiste.
    let list: HistoryRecord[] = [];
    try {
      await saveAnalysis(store, {
        url: 'https://lbc.fr/ad/3',
        title: 'T4',
        result: polluted,
        savedAt: 1_700_000_000_000,
      });
      list = await listAnalyses(store);
    } catch (err) {
      expect((err as Error).message).toMatch(/raw_text|image_urls|photos|text/);
      return;
    }
    // Si pas d'erreur : au moins 1 entree, et sa serialisation est expurgee.
    expect(list.length).toBeGreaterThan(0);
    expect(JSON.stringify(list)).not.toMatch(
      /"(raw_text|image_urls|photos|text)"/,
    );
  });
});

// =====================================================================
// AC3 — Dedup par URL : meme URL normalisee -> mise a jour + remontee en tete.
// =====================================================================
describe('AC3 — dedup par URL (update + remontee en tete, pas de doublon)', () => {
  it('AC3 : 3 entrees distinctes, re-save d une URL existante (query differente) -> meme cardinalite, maj, en tete', async () => {
    const base = 1_700_000_000_000;
    await saveAnalysis(store, {
      url: 'https://lbc.fr/ad/100',
      title: 'A',
      result: makeResult(10),
      savedAt: base + 1,
    });
    await saveAnalysis(store, {
      url: 'https://lbc.fr/ad/200',
      title: 'B',
      result: makeResult(20),
      savedAt: base + 2,
    });
    await saveAnalysis(store, {
      url: 'https://lbc.fr/ad/300',
      title: 'C',
      result: makeResult(30),
      savedAt: base + 3,
    });

    // Re-save de l'URL /ad/200 mais avec une query differente (meme bien §5.2).
    await saveAnalysis(store, {
      url: 'https://lbc.fr/ad/200?utm=campaign',
      title: 'B mis a jour',
      result: makeResult(99),
      savedAt: base + 4,
    });

    const list = await listAnalyses(store);
    // Pas de 4e entree : dedup.
    expect(list).toHaveLength(3);
    // L'entree mise a jour est en TETE.
    expect(list[0].title).toBe('B mis a jour');
    expect(list[0].result.global_score).toBe(99);
    expect(list[0].savedAt).toBe(base + 4);
    // Une seule entree porte ce bien.
    const sameBien = list.filter(
      (r) => normalizeUrlKey(r.url) === normalizeUrlKey('https://lbc.fr/ad/200'),
    );
    expect(sameBien).toHaveLength(1);
  });
});

// =====================================================================
// AC4 — normalizeUrlKey / id : egalite par URL normalisee, distinction sinon.
// =====================================================================
describe('AC4 — normalizeUrlKey + id', () => {
  it('AC4 : query/fragment ignores -> meme cle', () => {
    expect(normalizeUrlKey('https://lbc.fr/ad/123?utm=x')).toBe(
      normalizeUrlKey('https://lbc.fr/ad/123#photo'),
    );
  });

  it('AC4 : URLs de chemins differents -> cles distinctes', () => {
    expect(normalizeUrlKey('https://lbc.fr/ad/123')).not.toBe(
      normalizeUrlKey('https://lbc.fr/ad/999'),
    );
  });

  it('AC4 : host insensible a la casse -> meme cle', () => {
    expect(normalizeUrlKey('https://LBC.FR/ad/123')).toBe(
      normalizeUrlKey('https://lbc.fr/ad/123'),
    );
  });

  it('AC4 : buildRecord -> meme id pour meme URL normalisee, id distinct sinon', () => {
    const r1 = buildRecord({
      url: 'https://lbc.fr/ad/123?utm=a',
      title: 'X',
      result: makeResult(),
      savedAt: 1,
    });
    const r2 = buildRecord({
      url: 'https://lbc.fr/ad/123#frag',
      title: 'Y',
      result: makeResult(),
      savedAt: 2,
    });
    const r3 = buildRecord({
      url: 'https://lbc.fr/ad/999',
      title: 'Z',
      result: makeResult(),
      savedAt: 3,
    });
    expect(r1.id).toBe(r2.id);
    expect(r1.id).not.toBe(r3.id);
  });
});

// =====================================================================
// AC5 — Plafond EXACT 50 / 51e -> eviction de la plus ancienne. Bornes 50 ET 51.
// =====================================================================
describe('AC5 — plafond exact 50 (bornes 50 et 51)', () => {
  it('AC5 : constante HISTORY_CAP vaut exactement 50', () => {
    expect(HISTORY_CAP).toBe(50);
  });

  it('AC5 : 50 entrees distinctes -> exactement 50, la plus ancienne presente', async () => {
    const base = 1_700_000_000_000;
    for (let i = 0; i < 50; i++) {
      await saveAnalysis(store, {
        url: `https://lbc.fr/ad/${i}`,
        title: `T${i}`,
        result: makeResult(i),
        savedAt: base + i, // croissants
      });
    }
    const list = await listAnalyses(store);
    expect(list).toHaveLength(50);
    // La plus ancienne (i=0, savedAt minimal) est PRESENTE.
    expect(
      list.some(
        (r) => normalizeUrlKey(r.url) === normalizeUrlKey('https://lbc.fr/ad/0'),
      ),
    ).toBe(true);
  });

  it('AC5 : 51e entree (plus recente) -> 50, plus ancienne ABSENTE, 51e en tete', async () => {
    const base = 1_700_000_000_000;
    for (let i = 0; i < 51; i++) {
      await saveAnalysis(store, {
        url: `https://lbc.fr/ad/${i}`,
        title: `T${i}`,
        result: makeResult(i),
        savedAt: base + i, // croissants -> i=0 est la plus ancienne, i=50 la plus recente
      });
    }
    const list = await listAnalyses(store);
    expect(list).toHaveLength(50);
    // La 1re inseree (i=0, plus ancienne) est EVINCEE.
    expect(
      list.some(
        (r) => normalizeUrlKey(r.url) === normalizeUrlKey('https://lbc.fr/ad/0'),
      ),
    ).toBe(false);
    // La 51e (i=50, plus recente) est en TETE.
    expect(normalizeUrlKey(list[0].url)).toBe(
      normalizeUrlKey('https://lbc.fr/ad/50'),
    );
  });
});

// =====================================================================
// AC6 — Tri plus recent d'abord (sequence exacte des savedAt decroissants).
// =====================================================================
describe('AC6 — tri plus recent d abord', () => {
  it('AC6 : insertion en ordre savedAt melange -> sortie strictement decroissante', async () => {
    const inserts = [
      { url: 'https://lbc.fr/ad/a', savedAt: 300 },
      { url: 'https://lbc.fr/ad/b', savedAt: 100 },
      { url: 'https://lbc.fr/ad/c', savedAt: 500 },
      { url: 'https://lbc.fr/ad/d', savedAt: 200 },
      { url: 'https://lbc.fr/ad/e', savedAt: 400 },
    ];
    for (const ins of inserts) {
      await saveAnalysis(store, {
        url: ins.url,
        title: ins.url,
        result: makeResult(),
        savedAt: ins.savedAt,
      });
    }
    const list = await listAnalyses(store);
    expect(list.map((r) => r.savedAt)).toEqual([500, 400, 300, 200, 100]);
  });
});

// =====================================================================
// AC7 — Titre borne : 79/80/81 exacts + repli sur ""/null/undefined/"\n\n".
// =====================================================================
describe('AC7 — deriveTitle borne + repli', () => {
  it('AC7 : constante TITLE_MAX_LENGTH vaut exactement 80', () => {
    expect(TITLE_MAX_LENGTH).toBe(80);
  });

  it('AC7 : 1re ligne de 81 caracteres -> tronque a exactement 80 (les 80 premiers)', () => {
    const line = 'a'.repeat(81);
    const out = deriveTitle(line);
    expect(out).toHaveLength(80);
    expect(out).toBe('a'.repeat(80));
  });

  it('AC7 : 1re ligne de 80 caracteres -> inchangee (80)', () => {
    const line = 'b'.repeat(80);
    expect(deriveTitle(line)).toBe(line);
    expect(deriveTitle(line)).toHaveLength(80);
  });

  it('AC7 : 1re ligne de 79 caracteres -> inchangee (79)', () => {
    const line = 'c'.repeat(79);
    expect(deriveTitle(line)).toBe(line);
    expect(deriveTitle(line)).toHaveLength(79);
  });

  it('AC7 : prend la 1re ligne NON vide, espaces de bord retires', () => {
    expect(deriveTitle('\n   Appartement T3 lumineux   \nLigne 2')).toBe(
      'Appartement T3 lumineux',
    );
  });

  it('AC7 : repli "Analyse sans titre" sur entrees vides/nulles', () => {
    expect(deriveTitle('')).toBe('Analyse sans titre');
    expect(deriveTitle(null)).toBe('Analyse sans titre');
    expect(deriveTitle(undefined)).toBe('Analyse sans titre');
    expect(deriveTitle('\n\n')).toBe('Analyse sans titre');
    // jamais une chaine vide.
    expect(deriveTitle('')).not.toBe('');
  });
});

// =====================================================================
// AC8 — Suppression unitaire + id inexistant sans throw.
// =====================================================================
describe('AC8 — removeAnalysis', () => {
  async function seedThree(): Promise<HistoryRecord[]> {
    const base = 1_700_000_000_000;
    await saveAnalysis(store, {
      url: 'https://lbc.fr/ad/1',
      title: 'Un',
      result: makeResult(1),
      savedAt: base + 1,
    });
    await saveAnalysis(store, {
      url: 'https://lbc.fr/ad/2',
      title: 'Deux',
      result: makeResult(2),
      savedAt: base + 2,
    });
    await saveAnalysis(store, {
      url: 'https://lbc.fr/ad/3',
      title: 'Trois',
      result: makeResult(3),
      savedAt: base + 3,
    });
    return listAnalyses(store);
  }

  it('AC8 : retire l entree ciblee, conserve les autres triees', async () => {
    const list = await seedThree();
    const id2 = list.find((r) => r.title === 'Deux')!.id;

    await removeAnalysis(store, id2);
    const after = await listAnalyses(store);

    expect(after).toHaveLength(2);
    expect(after.some((r) => r.id === id2)).toBe(false);
    expect(after.map((r) => r.title)).toEqual(['Trois', 'Un']); // tri preserve
  });

  it('AC8 : id inexistant -> pas de throw, liste inchangee', async () => {
    await seedThree();
    await expect(
      removeAnalysis(store, 'id-qui-n-existe-pas'),
    ).resolves.not.toThrow();
    const after = await listAnalyses(store);
    expect(after).toHaveLength(3);
  });
});

// =====================================================================
// AC9 — Tout effacer -> [].
// =====================================================================
describe('AC9 — clearAnalyses', () => {
  it('AC9 : N entrees -> clear -> liste vide', async () => {
    const base = 1_700_000_000_000;
    for (let i = 0; i < 4; i++) {
      await saveAnalysis(store, {
        url: `https://lbc.fr/ad/${i}`,
        title: `T${i}`,
        result: makeResult(i),
        savedAt: base + i,
      });
    }
    expect(await listAnalyses(store)).toHaveLength(4);

    await clearAnalyses(store);
    expect(await listAnalyses(store)).toEqual([]);
  });
});

// =====================================================================
// AC10 — parseRecords defensif : entrees corrompues ignorees, pas d exception.
// =====================================================================
describe('AC10 — parseRecords defensif', () => {
  function validRaw(): unknown {
    return buildRecord({
      url: 'https://lbc.fr/ad/ok',
      title: 'Valide',
      result: makeResult(),
      savedAt: 1_700_000_000_000,
    });
  }

  it('AC10 : entree non-objet / null ignorees, entree valide conservee', () => {
    const out = parseRecords([null, 42, 'cassee', validRaw()]);
    expect(out).toHaveLength(1);
    expect(out[0].url).toBe('https://lbc.fr/ad/ok');
  });

  it('AC10 : champ obligatoire manquant -> ignore (pas d exception)', () => {
    const broken = { id: 'x', url: 'https://lbc.fr/ad/z' }; // pas de result/title/savedAt
    expect(() => parseRecords([broken, validRaw()])).not.toThrow();
    expect(parseRecords([broken, validRaw()])).toHaveLength(1);
  });

  it('AC10 : schemaVersion inconnu -> ignore', () => {
    const wrongVersion = {
      ...(validRaw() as Record<string, unknown>),
      schemaVersion: 999,
    };
    const out = parseRecords([wrongVersion]);
    expect(out).toEqual([]);
  });

  it('AC10 : cle interdite presente -> entree rejetee (pas acceptee)', () => {
    const withForbidden = {
      ...(validRaw() as Record<string, unknown>),
      raw_text: 'CONTENU INTERDIT',
    };
    const out = parseRecords([withForbidden]);
    expect(out).toEqual([]);
  });

  it('AC10 : entree totalement illisible / non-tableau -> [] sans throw', () => {
    expect(() => parseRecords('JSON casse {{{')).not.toThrow();
    expect(parseRecords('JSON casse {{{')).toEqual([]);
    expect(parseRecords(null)).toEqual([]);
    expect(parseRecords(undefined)).toEqual([]);
    expect(parseRecords({})).toEqual([]);
  });
});

// =====================================================================
// AC11 — Erreur de store : la NATURE de l erreur est asserte (pas un throw nu).
// =====================================================================
describe('AC11 — erreur de store en read/write : nature de l erreur', () => {
  it('AC11 : read() rejette -> listAnalyses rejette avec un message identifiant la lecture/store', async () => {
    const failing = new FailingReadStore();
    await expect(listAnalyses(failing)).rejects.toThrow(/read|store|sqlite/i);
    // interdiction d un message de stub generique (anti faux-vert).
    await expect(listAnalyses(failing)).rejects.not.toThrow(/NOT_IMPLEMENTED/);
  });

  it('AC11 : write() rejette -> saveAnalysis rejette avec un message identifiant l ecriture/store', async () => {
    const failing = new FailingWriteStore();
    await expect(
      saveAnalysis(failing, {
        url: 'https://lbc.fr/ad/1',
        title: 'T',
        result: makeResult(),
        savedAt: 1_700_000_000_000,
      }),
    ).rejects.toThrow(/write|store|sqlite/i);
    await expect(
      saveAnalysis(failing, {
        url: 'https://lbc.fr/ad/1',
        title: 'T',
        result: makeResult(),
        savedAt: 1_700_000_000_000,
      }),
    ).rejects.not.toThrow(/NOT_IMPLEMENTED/);
  });

  it('AC11 (contraste) : store SAIN -> listAnalyses/saveAnalysis n emettent AUCUNE erreur', async () => {
    await expect(listAnalyses(store)).resolves.not.toThrow();
    await expect(
      saveAnalysis(store, {
        url: 'https://lbc.fr/ad/sain',
        title: 'OK',
        result: makeResult(),
        savedAt: 1_700_000_000_000,
      }),
    ).resolves.not.toThrow();
  });
});

// =====================================================================
// AC12 — Invariant "strictement local" : aucun import reseau dans history.ts.
// =====================================================================
describe('AC12 — aucun import reseau dans history.ts (statique)', () => {
  const fs = require('fs') as typeof import('fs');
  const path = require('path') as typeof import('path');
  const source = fs.readFileSync(
    path.join(__dirname, 'history.ts'),
    'utf8',
  );

  it('AC12 : history.ts n importe pas analyzeApi / config, ni fetch, ni l endpoint', () => {
    expect(source).not.toMatch(/from\s+['"]\.\/analyzeApi['"]/);
    expect(source).not.toMatch(/from\s+['"]\.\/config['"]/);
    // pas d'appel reseau direct.
    expect(source).not.toMatch(/\bfetch\s*\(/);
    // pas de reference a la facade d analyse ni a l endpoint.
    expect(source).not.toMatch(/analyzeListing/);
    expect(source).not.toMatch(/\/analyze\b/);
  });
});

// =====================================================================
// AC13 — Inertie reseau prouvee sur la dependance TERMINALE + contraste causal.
// =====================================================================
describe('AC13 — inertie reseau (fetch) + contraste', () => {
  const realFetch = global.fetch;
  let savedApiUrl: string | undefined;

  beforeEach(() => {
    savedApiUrl = process.env.EXPO_PUBLIC_API_URL;
    process.env.EXPO_PUBLIC_API_URL = 'https://api.test.local';
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

  it('AC13 : save/list/remove/clear -> fetch JAMAIS appele (call_count === 0)', async () => {
    const fetchMock = jest.fn();
    global.fetch = fetchMock as unknown as typeof fetch;

    const base = 1_700_000_000_000;
    const saved = await saveAnalysis(store, {
      url: 'https://lbc.fr/ad/1',
      title: 'T',
      result: makeResult(),
      savedAt: base,
    });
    await listAnalyses(store);
    const id = saved[0]?.id ?? (await listAnalyses(store))[0]?.id;
    if (id) {
      await removeAnalysis(store, id);
    }
    await clearAnalyses(store);

    expect(fetchMock).toHaveBeenCalledTimes(0);
  });

  it('AC13 (contraste) : le MEME fetch mocke, appele via analyzeListing, INCREMENTE le compteur', async () => {
    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => makeResult(),
    });
    global.fetch = fetchMock as unknown as typeof fetch;

    await analyzeListing('texte', [
      'https://img.leboncoin.fr/x.jpg?rule=ad-large',
    ]);

    // Preuve que le garde-fou DETECTERAIT un appel reseau s il survenait.
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

// =====================================================================
// AC14 — Isolation d etat entre tests (store reinitialise en beforeEach).
// L ORDRE de ces deux tests importe : le 1er ecrit, le 2nd doit demarrer vide.
// =====================================================================
describe('AC14 — isolation d etat entre tests', () => {
  it('AC14 (1/2) : insere une entree dans le store de test', async () => {
    await saveAnalysis(store, {
      url: 'https://lbc.fr/ad/fuite',
      title: 'Ne doit pas fuiter',
      result: makeResult(),
      savedAt: 1_700_000_000_000,
    });
    expect(await listAnalyses(store)).toHaveLength(1);
  });

  it('AC14 (2/2) : le test suivant demarre sur un store VIDE (aucune fuite)', async () => {
    expect(await listAnalyses(store)).toEqual([]);
  });
});
