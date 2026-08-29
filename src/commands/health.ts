import { Command } from "commander";
import { parseHealthExport } from "../lib/health.js";
import { insertHealthRecords, healthSummary, listHealthRecords } from "../lib/store.js";
import { printTable } from "../lib/output.js";

const BATCH_SIZE = 500;

export function registerHealthCommands(program: Command): void {
  const health = program.command("health").description("import and query Apple Health data");

  health
    .command("import")
    .description("import records from an Apple Health export.xml file")
    .argument("<file>", "path to export.xml (unzip export.zip from the Health app first)")
    .action(async (file: string) => {
      console.log(`Parsing ${file}...`);
      const { records, skipped } = await parseHealthExport(file);
      console.log(`Parsed ${records.length} records (${skipped} skipped, missing/invalid fields).`);
      if (records.length === 0) {
        console.log("Nothing to import.");
        return;
      }
      let imported = 0;
      for (let i = 0; i < records.length; i += BATCH_SIZE) {
        const batch = records.slice(i, i + BATCH_SIZE);
        imported += await insertHealthRecords(batch);
        process.stdout.write(`\rImported ${imported}/${records.length}...`);
      }
      console.log(`\nDone. Imported ${imported} records.`);
    });

  health
    .command("summary")
    .description("show record counts by type")
    .action(async () => {
      const rows = await healthSummary();
      printTable(
        rows.map((r) => ({
          type: r.type,
          count: String(r.count),
          first: r.firstDate,
          last: r.lastDate,
        })),
      );
    });

  health
    .command("list")
    .description("list imported health records")
    .option("-t, --type <type>", "filter by record type, e.g. HKQuantityTypeIdentifierStepCount")
    .option("-s, --since <date>", "only records starting on/after this ISO date")
    .option("-l, --limit <n>", "max rows to show", "50")
    .action(async (opts: { type?: string; since?: string; limit: string }) => {
      const rows = await listHealthRecords({
        type: opts.type,
        since: opts.since,
        limit: Number(opts.limit),
      });
      printTable(
        rows.map((r) => ({
          type: r.type,
          value: r.value,
          unit: r.unit ?? "",
          start: r.startDate,
          source: r.sourceName ?? "",
        })),
      );
    });
}
