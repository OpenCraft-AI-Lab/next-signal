import { Pool, type QueryResultRow } from "pg";

type AppGlobal = typeof globalThis & {
  nsPgPool?: Pool;
};

function normalizePostgresUrl(url: string): string {
  return url
    .replace(/^postgresql\+psycopg:\/\//, "postgresql://")
    .replace(/^postgres\+psycopg:\/\//, "postgres://");
}

function connectionString(): string {
  const raw = process.env.NEXT_SIGNAL_DATABASE_URL ?? process.env.DATABASE_URL;
  if (!raw) {
    throw new Error("DATABASE_URL or NEXT_SIGNAL_DATABASE_URL is required for dashboard DB reads");
  }
  return normalizePostgresUrl(raw);
}

function pool(): Pool {
  const g = globalThis as AppGlobal;
  g.nsPgPool ??= new Pool({ connectionString: connectionString() });
  return g.nsPgPool;
}

export async function query<T extends QueryResultRow>(
  sql: string,
  params: unknown[] = [],
): Promise<T[]> {
  const result = await pool().query<T>(sql, params);
  return result.rows;
}
