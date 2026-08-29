import { createReadStream } from "node:fs";
import sax from "sax";

export interface HealthRecord {
  type: string;
  sourceName: string | null;
  unit: string | null;
  value: string;
  startDate: string;
  endDate: string;
}

/**
 * Apple Health export.xml <Record> elements carry dates like
 * "2026-01-01 08:00:00 -0800" — parseable by Date, but not valid ISO 8601,
 * so records with unparseable dates are dropped rather than stored as
 * "Invalid Date".
 */
export function mapRecordAttributes(attrs: Record<string, string>): HealthRecord | null {
  if (!attrs.type || !attrs.value || !attrs.startDate || !attrs.endDate) {
    return null;
  }
  const startDate = new Date(attrs.startDate);
  const endDate = new Date(attrs.endDate);
  if (isNaN(startDate.getTime()) || isNaN(endDate.getTime())) {
    return null;
  }
  return {
    type: attrs.type,
    sourceName: attrs.sourceName ?? null,
    unit: attrs.unit ?? null,
    value: attrs.value,
    startDate: startDate.toISOString(),
    endDate: endDate.toISOString(),
  };
}

export async function parseHealthExport(
  filePath: string,
): Promise<{ records: HealthRecord[]; skipped: number }> {
  const records: HealthRecord[] = [];
  let skipped = 0;

  await new Promise<void>((resolve, reject) => {
    // strict mode (true) is required so tag/attribute names keep their real
    // XML casing ("Record", "startDate") — sax's non-strict mode uppercases
    // them instead, which is meant for lenient HTML parsing, not XML.
    const parser = sax.createStream(true, { trim: true });

    parser.on("opentag", (node) => {
      if (node.name !== "Record") return;
      const rec = mapRecordAttributes(node.attributes as Record<string, string>);
      if (rec) {
        records.push(rec);
      } else {
        skipped++;
      }
    });
    parser.on("error", reject);
    parser.on("end", () => resolve());

    const stream = createReadStream(filePath);
    stream.on("error", reject);
    stream.pipe(parser);
  });

  return { records, skipped };
}
