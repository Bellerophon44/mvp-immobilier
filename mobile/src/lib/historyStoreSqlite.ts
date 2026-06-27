// Adaptateur CONCRET du port HistoryStore (src/lib/history.ts) sur expo-sqlite.
// Famille B (device) : non teste Jest car dependant du module natif expo-sqlite.
// SPEC mobile-tranche-b-historique §3.2 / §4.3. La logique pure (dedup, plafond,
// tri, whitelist) reste dans history.ts : cet adaptateur ne fait que persister et
// reconstruire des HistoryRecord, puis DELEGUE la validation a parseRecords.

import * as SQLite from 'expo-sqlite';
import {
  HistoryRecord,
  HistoryStore,
  parseRecords,
} from './history';

const DATABASE_NAME = 'history.db';

// Schema EXACT §4.3 : aucune colonne pour le texte/photos d'annonce (§11.3).
// result_json porte JSON.stringify(HistoryRecord.result) — la whitelist de
// history.ts garantit l'absence de contenu tiers AVANT serialisation.
const CREATE_TABLE_SQL = `
CREATE TABLE IF NOT EXISTS history (
  id TEXT PRIMARY KEY NOT NULL,
  url TEXT NOT NULL,
  title TEXT NOT NULL,
  saved_at INTEGER NOT NULL,
  schema_version INTEGER NOT NULL,
  result_json TEXT NOT NULL
);
`;

interface HistoryRow {
  id: string;
  url: string;
  title: string;
  saved_at: number;
  schema_version: number;
  result_json: string;
}

// Erreur nommee : l'app gere le repli (liste vide / message lisible) plus haut
// sans crasher (AC-B8). La nature de l'echec est portee par le message.
export class HistoryStoreError extends Error {
  constructor(message: string, options?: { cause?: unknown }) {
    super(message);
    this.name = 'HistoryStoreError';
    if (options?.cause !== undefined) {
      // why: conserver la cause native sqlite pour le diagnostic device.
      (this as { cause?: unknown }).cause = options.cause;
    }
  }
}

// Adaptateur sqlite : ouvre la base une seule fois (handle memorise) et cree la
// table idempotemment. read() reconstruit les enregistrements bruts puis delegue
// a parseRecords ; write() remplace l'ensemble dans une transaction.
export class SqliteHistoryStore implements HistoryStore {
  private dbPromise: Promise<SQLite.SQLiteDatabase> | null = null;

  private async getDb(): Promise<SQLite.SQLiteDatabase> {
    if (this.dbPromise === null) {
      this.dbPromise = (async () => {
        try {
          const db = await SQLite.openDatabaseAsync(DATABASE_NAME);
          await db.execAsync(CREATE_TABLE_SQL);
          return db;
        } catch (err) {
          // why: ne pas memoriser une promesse rejetee, sinon toute lecture
          // ulterieure echouerait sans nouvelle tentative d'ouverture.
          this.dbPromise = null;
          throw new HistoryStoreError(
            `history sqlite open failed: ${(err as Error).message}`,
            { cause: err },
          );
        }
      })();
    }
    return this.dbPromise;
  }

  async read(): Promise<HistoryRecord[]> {
    let rows: HistoryRow[];
    try {
      const db = await this.getDb();
      rows = await db.getAllAsync<HistoryRow>(
        'SELECT id, url, title, saved_at, schema_version, result_json FROM history',
      );
    } catch (err) {
      if (err instanceof HistoryStoreError) {
        throw err;
      }
      throw new HistoryStoreError(
        `history sqlite read failed: ${(err as Error).message}`,
        { cause: err },
      );
    }
    // Reconstruction des enregistrements bruts ; la validation/whitelist est
    // DELEGUEE a parseRecords (source unique de verite). Un result_json illisible
    // produit un enregistrement que parseRecords ecartera (parse defensif AC10).
    const raw = rows.map((row) => ({
      schemaVersion: row.schema_version,
      id: row.id,
      url: row.url,
      title: row.title,
      savedAt: row.saved_at,
      result: parseResultJson(row.result_json),
    }));
    return parseRecords(raw);
  }

  async write(records: HistoryRecord[]): Promise<void> {
    try {
      const db = await this.getDb();
      await db.withTransactionAsync(async () => {
        await db.execAsync('DELETE FROM history');
        for (const r of records) {
          await db.runAsync(
            'INSERT INTO history (id, url, title, saved_at, schema_version, result_json) VALUES (?, ?, ?, ?, ?, ?)',
            r.id,
            r.url,
            r.title,
            r.savedAt,
            r.schemaVersion,
            JSON.stringify(r.result),
          );
        }
      });
    } catch (err) {
      if (err instanceof HistoryStoreError) {
        throw err;
      }
      throw new HistoryStoreError(
        `history sqlite write failed: ${(err as Error).message}`,
        { cause: err },
      );
    }
  }
}

// result_json corrompu -> objet sentinelle vide ; parseRecords rejettera l'entree
// (result non conforme) sans lever, conformement au parse defensif (AC10).
function parseResultJson(json: string): unknown {
  try {
    return JSON.parse(json);
  } catch {
    return {};
  }
}
