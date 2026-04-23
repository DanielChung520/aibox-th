/**
 * @file        DuckDB-WASM 瀏覽器端 Cache Service
 * @description 單例模式封裝 DuckDB-WASM，支援從 JSON 建表、SQL 查詢、篩選/排序/翻頁
 * @lastUpdate  2026-04-16 10:51:40
 * @author      Daniel Chung
 * @version     1.0.0
 */

import * as duckdb from '@duckdb/duckdb-wasm';

// Vite 專用：以 URL 形式導入 Worker 與 WASM
import duckdb_wasm from '@duckdb/duckdb-wasm/dist/duckdb-mvp.wasm?url';
import mvp_worker from '@duckdb/duckdb-wasm/dist/duckdb-browser-mvp.worker.js?url';
import duckdb_wasm_eh from '@duckdb/duckdb-wasm/dist/duckdb-eh.wasm?url';
import eh_worker from '@duckdb/duckdb-wasm/dist/duckdb-browser-eh.worker.js?url';

const MANUAL_BUNDLES: duckdb.DuckDBBundles = {
  mvp: {
    mainModule: duckdb_wasm,
    mainWorker: mvp_worker,
  },
  eh: {
    mainModule: duckdb_wasm_eh,
    mainWorker: eh_worker,
  },
};

/** 表 cache 元資料 */
interface TableCacheMeta {
  cachedAt: string;     // ISO 時間戳
  rowCount: number;
  tableId: string;
}

class DuckDBWasmService {
  private static instance: DuckDBWasmService;
  private db: duckdb.AsyncDuckDB | null = null;
  private worker: Worker | null = null;
  private initPromise: Promise<void> | null = null;
  /** 記錄每張表的 cache 時間 */
  private tableMeta: Map<string, TableCacheMeta> = new Map();

  private constructor() {}

  static getInstance(): DuckDBWasmService {
    if (!DuckDBWasmService.instance) {
      DuckDBWasmService.instance = new DuckDBWasmService();
    }
    return DuckDBWasmService.instance;
  }

  /** 初始化 DuckDB-WASM（只執行一次，重入安全） */
  async init(): Promise<void> {
    if (this.db) return;
    if (this.initPromise) return this.initPromise;

    this.initPromise = this._doInit();
    return this.initPromise;
  }

  private async _doInit(): Promise<void> {
    try {
      const bundle = await duckdb.selectBundle(MANUAL_BUNDLES);

      if (!bundle.mainWorker) {
        throw new Error('No DuckDB worker bundle available');
      }
      this.worker = new Worker(bundle.mainWorker);
      const logger = new duckdb.ConsoleLogger(duckdb.LogLevel.WARNING);
      this.db = new duckdb.AsyncDuckDB(logger, this.worker);
      await this.db.instantiate(bundle.mainModule, bundle.pthreadWorker);

      console.log('[DuckDB-WASM] initialized');
    } catch (err) {
      this.initPromise = null;
      throw err;
    }
  }

  /** 取得連線 */
  private async connect(): Promise<duckdb.AsyncDuckDBConnection> {
    if (!this.db) throw new Error('DuckDB-WASM not initialized');
    return this.db.connect();
  }

  /**
   * 將 JSON 資料載入為一張表（DROP + CREATE）
   * tableName 會被 sanitize 為 safe identifier
   */
  async loadTable(
    tableId: string,
    rows: Record<string, unknown>[],
  ): Promise<void> {
    await this.init();
    if (!this.db) throw new Error('DuckDB-WASM not initialized');

    const safeName = this.safeTableName(tableId);
    const conn = await this.connect();
    try {
      await conn.query(`DROP TABLE IF EXISTS ${safeName}`);

      if (rows.length === 0) {
        // 空表：建一張空結構
        await conn.query(`CREATE TABLE ${safeName} (__empty INT)`);
        this.tableMeta.set(tableId, {
          cachedAt: new Date().toISOString(),
          rowCount: 0,
          tableId,
        });
        return;
      }

      // 用 DuckDB 的 JSON 自動推斷建表
      const filename = `${safeName}.json`;
      await this.db.registerFileText(filename, JSON.stringify(rows));
      await conn.insertJSONFromPath(filename, { name: safeName, schema: 'main', create: true });

      this.tableMeta.set(tableId, {
        cachedAt: new Date().toISOString(),
        rowCount: rows.length,
        tableId,
      });
      console.log(`[DuckDB-WASM] table "${safeName}" loaded: ${rows.length} rows`);
    } finally {
      await conn.close();
    }
  }

  /** 查詢（回傳 JSON array） */
  async query<T = Record<string, unknown>>(sql: string): Promise<T[]> {
    await this.init();
    const conn = await this.connect();
    try {
      const result = await conn.query(sql);
      return this.arrowToJSON<T>(result);
    } finally {
      await conn.close();
    }
  }

  /** 取得某表的 row count（用 DuckDB 計算） */
  async countRows(tableId: string): Promise<number> {
    const safeName = this.safeTableName(tableId);
    const rows = await this.query<{ cnt: number }>(`SELECT COUNT(*)::INTEGER AS cnt FROM ${safeName}`);
    return rows[0]?.cnt ?? 0;
  }

  /** 檢查表是否已 cache */
  hasTable(tableId: string): boolean {
    return this.tableMeta.has(tableId);
  }

  /** 取得 cache 元資料 */
  getTableMeta(tableId: string): TableCacheMeta | undefined {
    return this.tableMeta.get(tableId);
  }

  /** 清除某張表的 cache */
  async dropTable(tableId: string): Promise<void> {
    await this.init();
    const safeName = this.safeTableName(tableId);
    const conn = await this.connect();
    try {
      await conn.query(`DROP TABLE IF EXISTS ${safeName}`);
      this.tableMeta.delete(tableId);
    } finally {
      await conn.close();
    }
  }

  /** table name → safe SQL identifier：只保留英數和底線 */
  private safeTableName(tableId: string): string {
    return `t_${tableId.replace(/[^a-zA-Z0-9_]/g, '_')}`;
  }

  /** Arrow Table → JSON（處理 BigInt） */
  private arrowToJSON<T>(table: { toArray(): unknown[] }): T[] {
    return table.toArray().map((row: unknown) => {
      const r = row as Record<string, unknown>;
      const obj: Record<string, unknown> = {};
      for (const key of Object.keys(r)) {
        const v = r[key];
        obj[key] = typeof v === 'bigint' ? Number(v) : v;
      }
      return obj as T;
    });
  }

  /** 銷毀（頁面卸載時可選呼叫） */
  async terminate(): Promise<void> {
    if (this.db) await this.db.terminate();
    if (this.worker) this.worker.terminate();
    this.db = null;
    this.worker = null;
    this.initPromise = null;
    this.tableMeta.clear();
  }
}

export const duckdbWasm = DuckDBWasmService.getInstance();
