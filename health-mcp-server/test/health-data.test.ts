import { describe, expect, it } from "vitest";
import { parseHealthEntries, summarizeHealthRecords } from "../src/services/health-data.js";
import type { HealthRecord } from "../src/types.js";

describe("parseHealthEntries", () => {
  it("parses a valid records array", () => {
    const entries = parseHealthEntries({
      records: [{ type: "steps", value: 8123, unit: "count", recordedAt: "2026-08-28T10:00:00Z" }],
    });
    expect(entries).toEqual([
      { type: "steps", value: 8123, unit: "count", recordedAt: "2026-08-28T10:00:00Z" },
    ]);
  });

  it("rejects a payload without a records array", () => {
    expect(() => parseHealthEntries({})).toThrow(/records/);
    expect(() => parseHealthEntries(null)).toThrow(/records/);
  });

  it("rejects a record missing required fields", () => {
    expect(() =>
      parseHealthEntries({ records: [{ value: 1, unit: "kg", recordedAt: "2026-08-28T10:00:00Z" }] }),
    ).toThrow(/"type"/);
    expect(() =>
      parseHealthEntries({ records: [{ type: "weight", unit: "kg", recordedAt: "2026-08-28T10:00:00Z" }] }),
    ).toThrow(/"value"/);
    expect(() =>
      parseHealthEntries({ records: [{ type: "weight", value: 70, unit: "kg", recordedAt: "not-a-date" }] }),
    ).toThrow(/recordedAt/);
  });
});

describe("summarizeHealthRecords", () => {
  const records: HealthRecord[] = [
    {
      id: "hrec_1",
      type: "steps",
      value: 1000,
      unit: "count",
      recordedAt: "2026-08-27T00:00:00Z",
      source: "apple_health",
      importedAt: "2026-08-28T00:00:00Z",
    },
    {
      id: "hrec_2",
      type: "steps",
      value: 3000,
      unit: "count",
      recordedAt: "2026-08-28T00:00:00Z",
      source: "apple_health",
      importedAt: "2026-08-28T00:00:00Z",
    },
    {
      id: "hrec_3",
      type: "weight",
      value: 70,
      unit: "kg",
      recordedAt: "2026-08-28T00:00:00Z",
      source: "google_health_connect",
      importedAt: "2026-08-28T00:00:00Z",
    },
  ];

  it("aggregates per record type, sorted by type", () => {
    const summaries = summarizeHealthRecords(records);
    expect(summaries.map((s) => s.type)).toEqual(["steps", "weight"]);

    const steps = summaries[0];
    expect(steps.count).toBe(2);
    expect(steps.min).toBe(1000);
    expect(steps.max).toBe(3000);
    expect(steps.avg).toBe(2000);
    expect(steps.latestValue).toBe(3000);
  });

  it("returns an empty list for no records", () => {
    expect(summarizeHealthRecords([])).toEqual([]);
  });
});
