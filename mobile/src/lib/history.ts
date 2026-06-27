// Logique PURE de l'historique d'analyses local. SPEC mobile-tranche-b-historique
// §3.3 / §4 / §5. Aucune dependance reseau ni sqlite : la persistance passe par
// le port HistoryStore injecte. Source unique de verite (dedup, plafond, tri,
// whitelist, derivation de titre, parse defensif).

import { ApiResult } from './types';

export const HISTORY_SCHEMA_VERSION = 1;
export const HISTORY_CAP = 50;
export const TITLE_MAX_LENGTH = 80;

const TITLE_FALLBACK = 'Analyse sans titre';

// Contenu tiers banni a TOUTE profondeur de l'enregistrement (§4.1 / §11.3) :
// un scrape/DOM pourrait pousser ces cles dans local_context, claims, etc.
const FORBIDDEN_KEYS_DEEP: readonly string[] = [
  'raw_text',
  'image_urls',
  'photos',
  'body',
];

// `text` est un cas special : interdit a AUCUN niveau (§4.1) AVEC une UNIQUE
// derogation positive — `result.local_context.claims[i].text`, qui est notre
// agregat d'analyse legitime. La detection est donc consciente du CHEMIN : on
// autorise la cle `text` SEULEMENT lorsque son parent direct est un element du
// tableau `claims`. Partout ailleurs (racine de result, local_context.text, sous
// n'importe quel autre objet/tableau), `text` est traitee comme interdite au
// meme titre que raw_text/image_urls/photos/body.
const FORBIDDEN_KEY_PATH_AWARE = 'text';
const CLAIMS_ARRAY_KEY = 'claims';

export interface HistoryRecord {
  schemaVersion: number;
  id: string;
  url: string;
  title: string;
  savedAt: number;
  result: ApiResult;
}

export interface HistoryStore {
  read(): Promise<HistoryRecord[]>;
  write(records: HistoryRecord[]): Promise<void>;
}

// Whitelist stricte des cles d'un enregistrement (cf. §4.1 / AC2).
export const ALLOWED_RECORD_KEYS: readonly string[] = [
  'schemaVersion',
  'id',
  'url',
  'title',
  'savedAt',
  'result',
];

export function deriveTitle(rawText: string | null | undefined): string {
  if (rawText === null || rawText === undefined) {
    return TITLE_FALLBACK;
  }
  for (const line of rawText.split('\n')) {
    const trimmed = line.trim();
    if (trimmed.length > 0) {
      return trimmed.slice(0, TITLE_MAX_LENGTH);
    }
  }
  return TITLE_FALLBACK;
}

export function normalizeUrlKey(url: string): string {
  try {
    const parsed = new URL(url);
    return parsed.origin.toLowerCase() + parsed.pathname;
  } catch {
    // Repli conservateur : URL non parsable conservee telle quelle (pas d'exception).
    return url;
  }
}

// Erreur nommee levee quand un result porte un champ de contenu tiers interdit.
// Le message identifie le champ pour rendre l'AC2 dynamique falsifiable (pas un
// throw nu) et tracer la cause.
export class ForbiddenFieldError extends Error {
  constructor(field: string) {
    super(`history record forbidden field: ${field}`);
    this.name = 'ForbiddenFieldError';
  }
}

// Detecte recursivement un champ de contenu tiers interdit dans une valeur, en
// etant CONSCIENT DU CHEMIN. raw_text/image_urls/photos/body sont bannis a TOUTE
// profondeur. `text` est banni partout SAUF lorsque l'objet courant est un
// element du tableau `claims` (derogation positive `claims[].text`). Le drapeau
// `parentIsClaimsItem` porte ce contexte : il est vrai quand on traverse un objet
// dont le parent direct etait la valeur d'une cle `claims` qui etait un tableau.
// Renvoie le nom du champ fautif, ou null si la valeur est propre.
function findForbiddenFieldDeep(
  value: unknown,
  parentIsClaimsItem: boolean,
): string | null {
  if (Array.isArray(value)) {
    for (const item of value) {
      // Les elements heritent du contexte du tableau (claims[] -> item de claims).
      const found = findForbiddenFieldDeep(item, parentIsClaimsItem);
      if (found !== null) {
        return found;
      }
    }
    return null;
  }
  if (value === null || typeof value !== 'object') {
    return null;
  }
  const obj = value as Record<string, unknown>;
  for (const key of Object.keys(obj)) {
    if (FORBIDDEN_KEYS_DEEP.includes(key)) {
      return key;
    }
    // `text` n'est tolere que comme propriete directe d'un item de claims.
    if (key === FORBIDDEN_KEY_PATH_AWARE && !parentIsClaimsItem) {
      return key;
    }
    // Le contenu d'une cle `claims` (tableau) marque ses elements comme items de
    // claims ; toute autre cle remet le contexte a faux (un `text` plus profond
    // sous claims[].something n'est PAS autorise).
    const childIsClaimsItems =
      key === CLAIMS_ARRAY_KEY && Array.isArray(obj[key]);
    const found = findForbiddenFieldDeep(obj[key], childIsClaimsItems);
    if (found !== null) {
      return found;
    }
  }
  return null;
}

// Garde-fou whitelist : le result ne doit porter, a AUCUN niveau, de champ de
// contenu tiers. La racine de result n'est jamais un item de claims, donc un
// `text` racine est interdit ; seul `local_context.claims[].text` est tolere
// (cf. findForbiddenFieldDeep, derogation positive §4.1).
function findForbiddenFieldInResult(result: ApiResult): string | null {
  if (result === null || typeof result !== 'object' || Array.isArray(result)) {
    return null;
  }
  return findForbiddenFieldDeep(result, false);
}

function assertNoForbiddenField(result: ApiResult): void {
  const forbidden = findForbiddenFieldInResult(result);
  if (forbidden !== null) {
    throw new ForbiddenFieldError(forbidden);
  }
}

export function buildRecord(input: {
  url: string;
  title: string;
  result: ApiResult;
  savedAt: number;
}): HistoryRecord {
  assertNoForbiddenField(input.result);
  return {
    schemaVersion: HISTORY_SCHEMA_VERSION,
    id: normalizeUrlKey(input.url),
    url: input.url,
    title: input.title,
    savedAt: input.savedAt,
    result: input.result,
  };
}

export function upsertRecord(
  existing: HistoryRecord[],
  record: HistoryRecord,
): HistoryRecord[] {
  const key = normalizeUrlKey(record.url);
  const deduped = existing.filter((r) => normalizeUrlKey(r.url) !== key);
  // L'enregistrement fraichement upserte passe en TETE avant le tri (§5.1) : le
  // tri par savedAt decroissant est stable, donc a savedAt EGAL l'upserte (place
  // en index 0) reste devant une entree existante de meme savedAt.
  deduped.unshift(record);
  deduped.sort((a, b) => b.savedAt - a.savedAt);
  return deduped.slice(0, HISTORY_CAP);
}

function isValidRecord(value: unknown): value is HistoryRecord {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) {
    return false;
  }
  const obj = value as Record<string, unknown>;
  for (const key of Object.keys(obj)) {
    if (!ALLOWED_RECORD_KEYS.includes(key)) {
      return false;
    }
  }
  if (obj.schemaVersion !== HISTORY_SCHEMA_VERSION) {
    return false;
  }
  if (typeof obj.id !== 'string') {
    return false;
  }
  if (typeof obj.url !== 'string') {
    return false;
  }
  if (typeof obj.title !== 'string') {
    return false;
  }
  if (typeof obj.savedAt !== 'number') {
    return false;
  }
  if (obj.result === null || typeof obj.result !== 'object') {
    return false;
  }
  // Whitelist en PROFONDEUR : une entree empoisonnee (champ interdit imbrique
  // dans result, ex. local_context.raw_text) doit etre rejetee au read() pour ne
  // pas etre rechargee telle quelle (§4.1 / §11.3). `claims[].text` reste valide.
  if (findForbiddenFieldInResult(obj.result as ApiResult) !== null) {
    return false;
  }
  return true;
}

export function parseRecords(raw: unknown): HistoryRecord[] {
  let items: unknown = raw;
  if (typeof items === 'string') {
    try {
      items = JSON.parse(items);
    } catch {
      return [];
    }
  }
  if (!Array.isArray(items)) {
    return [];
  }
  const valid: HistoryRecord[] = [];
  for (const item of items) {
    if (isValidRecord(item)) {
      valid.push(item);
    }
  }
  return valid;
}

export async function saveAnalysis(
  store: HistoryStore,
  input: { url: string; title: string; result: ApiResult; savedAt: number },
): Promise<HistoryRecord[]> {
  let existing: HistoryRecord[];
  try {
    existing = parseRecords(await store.read());
  } catch (err) {
    throw new Error(`history store read failed: ${(err as Error).message}`);
  }
  const next = upsertRecord(existing, buildRecord(input));
  try {
    await store.write(next);
  } catch (err) {
    throw new Error(`history store write failed: ${(err as Error).message}`);
  }
  return next;
}

export async function listAnalyses(store: HistoryStore): Promise<HistoryRecord[]> {
  let raw: HistoryRecord[];
  try {
    raw = await store.read();
  } catch (err) {
    throw new Error(`history store read failed: ${(err as Error).message}`);
  }
  return parseRecords(raw).sort((a, b) => b.savedAt - a.savedAt);
}

export async function removeAnalysis(
  store: HistoryStore,
  id: string,
): Promise<HistoryRecord[]> {
  let existing: HistoryRecord[];
  try {
    existing = parseRecords(await store.read());
  } catch (err) {
    throw new Error(`history store read failed: ${(err as Error).message}`);
  }
  const next = existing
    .filter((r) => r.id !== id)
    .sort((a, b) => b.savedAt - a.savedAt);
  try {
    await store.write(next);
  } catch (err) {
    throw new Error(`history store write failed: ${(err as Error).message}`);
  }
  return next;
}

export async function clearAnalyses(store: HistoryStore): Promise<void> {
  try {
    await store.write([]);
  } catch (err) {
    throw new Error(`history store write failed: ${(err as Error).message}`);
  }
}
