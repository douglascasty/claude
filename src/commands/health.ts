import { Command } from "commander";
import { readFileSync } from "node:fs";
import { loadState, saveState, newId } from "../lib/store.js";
import { printTable, fail } from "../lib/output.js";
import {
  HEALTH_PROVIDERS,
  isHealthProvider,
  parseHealthImport,
  summarizeHealthRecords,
  type HealthRecord,
  type ParsedHealthEntry,
} from "../lib/health.js";

export function registerHealthCommands(program: Command): void {
  const health = program
    .command("health")
    .description("connect and import personal health data (Apple Health, Google Health Connect)");

  health
    .command("connect")
    .description("record a connection to a health data provider")
    .argument("<provider>", `provider id (${HEALTH_PROVIDERS.join(", ")})`)
    .action((provider: string) => {
      if (!isHealthProvider(provider)) {
        fail(`unknown provider "${provider}". Choose one of: ${HEALTH_PROVIDERS.join(", ")}.`);
      }
      const state = loadState();
      state.healthConnection = { provider, connectedAt: new Date().toISOString() };
      saveState(state);
      console.log(`Connected to ${provider}.`);
      console.log(
        "Note: this CLI has no device-level access to HealthKit or Health Connect. " +
          "Export your data from the provider's app and import it with " +
          "`claude-console health import <file>`.",
      );
    });

  health
    .command("disconnect")
    .description("clear the local health provider connection")
    .action(() => {
      const state = loadState();
      if (!state.healthConnection) {
        console.log("No health provider connected.");
        return;
      }
      state.healthConnection = null;
      saveState(state);
      console.log("Disconnected.");
    });

  health
    .command("status")
    .description("show the current health connection and record count")
    .action(() => {
      const state = loadState();
      if (!state.healthConnection) {
        console.log("Not connected. Run `claude-console health connect <provider>`.");
        return;
      }
      console.log(`provider:  ${state.healthConnection.provider}`);
      console.log(`connected: ${state.healthConnection.connectedAt}`);
      console.log(`records:   ${state.healthRecords.length}`);
    });

  health
    .command("import")
    .description("import health records from a JSON export file")
    .argument("<file>", 'path to a JSON file shaped as { "records": [{ type, value, unit, recordedAt }] }')
    .action((file: string) => {
      const state = loadState();
      if (!state.healthConnection) {
        fail("no provider connected. Run `claude-console health connect <provider>` first.");
      }

      let raw: string;
      try {
        raw = readFileSync(file, "utf-8");
      } catch {
        fail(`could not read file "${file}".`);
      }

      let data: unknown;
      try {
        data = JSON.parse(raw);
      } catch {
        fail(`"${file}" is not valid JSON.`);
      }

      let entries: ParsedHealthEntry[];
      try {
        entries = parseHealthImport(data);
      } catch (err) {
        fail(err instanceof Error ? err.message : String(err));
      }

      const importedAt = new Date().toISOString();
      const provider = state.healthConnection.provider;
      const records: HealthRecord[] = entries.map((entry) => ({
        id: newId("hrec"),
        ...entry,
        source: provider,
        importedAt,
      }));
      state.healthRecords.push(...records);
      saveState(state);
      console.log(`Imported ${records.length} record(s) from "${file}".`);
    });

  health
    .command("list")
    .description("list imported health records")
    .option("-t, --type <type>", "filter by record type")
    .option("-l, --limit <n>", "limit number of rows shown", "20")
    .action((opts: { type?: string; limit: string }) => {
      const state = loadState();
      let records = state.healthRecords;
      if (opts.type) {
        records = records.filter((r) => r.type === opts.type);
      }
      const limit = Number.parseInt(opts.limit, 10);
      const sliced = [...records]
        .sort((a, b) => b.recordedAt.localeCompare(a.recordedAt))
        .slice(0, Number.isNaN(limit) ? records.length : limit);
      printTable(
        sliced.map((r) => ({
          type: r.type,
          value: String(r.value),
          unit: r.unit,
          recordedAt: r.recordedAt,
          source: r.source,
        })),
      );
    });

  health
    .command("summary")
    .description("show aggregate stats per record type")
    .action(() => {
      const state = loadState();
      const summaries = summarizeHealthRecords(state.healthRecords);
      printTable(
        summaries.map((s) => ({
          type: s.type,
          count: String(s.count),
          latest: `${s.latestValue} ${s.unit} (${s.latestAt})`,
          min: String(s.min),
          max: String(s.max),
          avg: s.avg.toFixed(2),
        })),
      );
    });
}
