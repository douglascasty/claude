import { describe, expect, it } from "vitest";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { mapRecordAttributes, parseHealthExport } from "../src/lib/health.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const fixture = join(__dirname, "fixtures", "sample-export.xml");

describe("mapRecordAttributes", () => {
  it("maps a valid record, converting dates to ISO", () => {
    const rec = mapRecordAttributes({
      type: "HKQuantityTypeIdentifierStepCount",
      sourceName: "iPhone",
      unit: "count",
      startDate: "2026-01-01 08:00:00 -0800",
      endDate: "2026-01-01 08:05:00 -0800",
      value: "120",
    });
    expect(rec).toEqual({
      type: "HKQuantityTypeIdentifierStepCount",
      sourceName: "iPhone",
      unit: "count",
      value: "120",
      startDate: "2026-01-01T16:00:00.000Z",
      endDate: "2026-01-01T16:05:00.000Z",
    });
  });

  it("returns null when a required field is missing", () => {
    expect(
      mapRecordAttributes({
        type: "HKQuantityTypeIdentifierStepCount",
        startDate: "2026-01-01 08:00:00 -0800",
        value: "120",
      }),
    ).toBeNull();
  });

  it("returns null when a date can't be parsed", () => {
    expect(
      mapRecordAttributes({
        type: "HKQuantityTypeIdentifierStepCount",
        startDate: "not-a-date",
        endDate: "also-not-a-date",
        value: "120",
      }),
    ).toBeNull();
  });

  it("defaults sourceName/unit to null when absent", () => {
    const rec = mapRecordAttributes({
      type: "HKQuantityTypeIdentifierStepCount",
      startDate: "2026-01-01 08:00:00 -0800",
      endDate: "2026-01-01 08:05:00 -0800",
      value: "120",
    });
    expect(rec?.sourceName).toBeNull();
    expect(rec?.unit).toBeNull();
  });
});

describe("parseHealthExport", () => {
  it("parses Record elements from a sample export.xml, skipping invalid ones", async () => {
    const { records, skipped } = await parseHealthExport(fixture);
    expect(records).toHaveLength(3);
    expect(skipped).toBe(1);
    expect(records[0]).toEqual({
      type: "HKQuantityTypeIdentifierStepCount",
      sourceName: "iPhone",
      unit: "count",
      value: "120",
      startDate: "2026-01-01T16:00:00.000Z",
      endDate: "2026-01-01T16:05:00.000Z",
    });
    expect(records[1].type).toBe("HKQuantityTypeIdentifierHeartRate");
  });

  it("rejects when the file doesn't exist", async () => {
    await expect(parseHealthExport(join(__dirname, "fixtures", "missing.xml"))).rejects.toThrow();
  });
});
