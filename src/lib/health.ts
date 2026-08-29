export type HealthProvider = "apple_health" | "google_health_connect";

export const HEALTH_PROVIDERS: HealthProvider[] = ["apple_health", "google_health_connect"];

export function isHealthProvider(value: string): value is HealthProvider {
  return (HEALTH_PROVIDERS as string[]).includes(value);
}

export interface HealthConnection {
  provider: HealthProvider;
  connectedAt: string;
}

export interface HealthRecord {
  id: string;
  type: string;
  value: number;
  unit: string;
  recordedAt: string;
  source: HealthProvider;
  importedAt: string;
}

export interface ParsedHealthEntry {
  type: string;
  value: number;
  unit: string;
  recordedAt: string;
}

/**
 * Parses the common export shape produced by both Apple Health and Google
 * Health Connect exporters once normalized to JSON: `{ "records": [...] }`.
 */
export function parseHealthImport(data: unknown): ParsedHealthEntry[] {
  if (typeof data !== "object" || data === null || !Array.isArray((data as Record<string, unknown>).records)) {
    throw new Error('expected a JSON object with a "records" array');
  }
  const records = (data as { records: unknown[] }).records;
  return records.map((raw, i) => {
    if (typeof raw !== "object" || raw === null) {
      throw new Error(`record at index ${i} is not an object`);
    }
    const r = raw as Record<string, unknown>;
    if (typeof r.type !== "string" || r.type.trim() === "") {
      throw new Error(`record at index ${i} is missing a "type" string`);
    }
    if (typeof r.value !== "number" || Number.isNaN(r.value)) {
      throw new Error(`record at index ${i} is missing a numeric "value"`);
    }
    if (typeof r.unit !== "string" || r.unit.trim() === "") {
      throw new Error(`record at index ${i} is missing a "unit" string`);
    }
    if (typeof r.recordedAt !== "string" || Number.isNaN(Date.parse(r.recordedAt))) {
      throw new Error(`record at index ${i} is missing a valid "recordedAt" ISO date string`);
    }
    return { type: r.type, value: r.value, unit: r.unit, recordedAt: r.recordedAt };
  });
}

export interface HealthSummary {
  type: string;
  count: number;
  unit: string;
  latestValue: number;
  latestAt: string;
  min: number;
  max: number;
  avg: number;
}

export function summarizeHealthRecords(records: HealthRecord[]): HealthSummary[] {
  const byType = new Map<string, HealthRecord[]>();
  for (const record of records) {
    const list = byType.get(record.type) ?? [];
    list.push(record);
    byType.set(record.type, list);
  }

  const summaries: HealthSummary[] = [];
  for (const [type, list] of byType) {
    const latest = [...list].sort((a, b) => a.recordedAt.localeCompare(b.recordedAt)).at(-1)!;
    const values = list.map((r) => r.value);
    summaries.push({
      type,
      count: list.length,
      unit: latest.unit,
      latestValue: latest.value,
      latestAt: latest.recordedAt,
      min: Math.min(...values),
      max: Math.max(...values),
      avg: values.reduce((a, b) => a + b, 0) / values.length,
    });
  }
  return summaries.sort((a, b) => a.type.localeCompare(b.type));
}
