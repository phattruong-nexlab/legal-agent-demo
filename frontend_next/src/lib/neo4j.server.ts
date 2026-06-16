import "server-only";
import neo4j, { Driver, Record as Neo4jRecord } from "neo4j-driver";

// Singleton driver across hot-reloads (Next dev re-imports modules).
const globalForNeo4j = globalThis as unknown as { _neo4jDriver?: Driver | null };

export function getDriver(): Driver | null {
  if (globalForNeo4j._neo4jDriver !== undefined) {
    return globalForNeo4j._neo4jDriver;
  }
  const uri = process.env.NEO4J_URI || "";
  if (!uri) {
    globalForNeo4j._neo4jDriver = null;
    return null;
  }
  const driver = neo4j.driver(
    uri,
    neo4j.auth.basic(
      process.env.NEO4J_USERNAME || "",
      process.env.NEO4J_PASSWORD || ""
    ),
    { disableLosslessIntegers: true }
  );
  globalForNeo4j._neo4jDriver = driver;
  return driver;
}

const DATABASE = () => process.env.NEO4J_DATABASE || undefined;

/** Run a query and return the raw neo4j records (for graph transforms). */
export async function runRecords(
  cypher: string,
  params: Record<string, unknown> = {}
): Promise<Neo4jRecord[]> {
  const drv = getDriver();
  if (!drv) return [];
  const session = drv.session({ database: DATABASE() });
  try {
    const res = await session.run(cypher, params);
    return res.records;
  } finally {
    await session.close();
  }
}

/** Recursively convert neo4j driver values (temporal, Node maps) to plain JS. */
export function toPlain(value: any): any {
  if (value === null || value === undefined) return value;
  if (
    neo4j.isDate(value) ||
    neo4j.isDateTime(value) ||
    neo4j.isLocalDateTime(value) ||
    neo4j.isTime(value) ||
    neo4j.isLocalTime(value) ||
    neo4j.isDuration(value)
  ) {
    return value.toString();
  }
  if (neo4j.isInt(value)) return value.toNumber();
  if (Array.isArray(value)) return value.map(toPlain);
  if (neo4j.isNode(value)) {
    const out: Record<string, any> = {};
    for (const [k, v] of Object.entries(value.properties)) out[k] = toPlain(v);
    return out;
  }
  if (typeof value === "object") {
    // plain map returned from Cypher
    const out: Record<string, any> = {};
    for (const [k, v] of Object.entries(value)) out[k] = toPlain(v);
    return out;
  }
  return value;
}

/** Run a query and return an array of plain JS objects (like Python run_dicts). */
export async function runDicts(
  cypher: string,
  params: Record<string, unknown> = {}
): Promise<Record<string, any>[]> {
  const records = await runRecords(cypher, params);
  return records.map((r) => {
    const obj: Record<string, any> = {};
    for (const key of r.keys) obj[key as string] = toPlain(r.get(key as string));
    return obj;
  });
}

/** Lightweight connectivity check, mirrors _connection_banner(). */
export async function pingNeo4j(): Promise<{ ok: boolean; error?: string }> {
  if (!process.env.NEO4J_URI) {
    return { ok: false, error: "NEO4J_URI chưa được cấu hình." };
  }
  const drv = getDriver();
  if (!drv) return { ok: false, error: "Driver chưa khởi tạo." };
  const session = drv.session({ database: DATABASE() });
  try {
    await session.run("RETURN 1");
    return { ok: true };
  } catch (e: any) {
    return { ok: false, error: String(e?.message || e) };
  } finally {
    await session.close();
  }
}
