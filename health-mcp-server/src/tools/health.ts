import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { readFileSync } from "node:fs";
import { z } from "zod";
import { HEALTH_PROVIDERS, CHARACTER_LIMIT, DEFAULT_LIST_LIMIT, MAX_LIST_LIMIT } from "../constants.js";
import { loadState, saveState, newRecordId } from "../services/store.js";
import { parseHealthEntries, summarizeHealthRecords } from "../services/health-data.js";
import type { HealthRecord, ParsedHealthEntry } from "../types.js";

enum ResponseFormat {
  MARKDOWN = "markdown",
  JSON = "json",
}

const ResponseFormatSchema = z
  .nativeEnum(ResponseFormat)
  .default(ResponseFormat.MARKDOWN)
  .describe("Output format: 'markdown' for a human-readable summary or 'json' for structured data");

function truncateNote(shown: number, total: number): string {
  return `\n\n_Response truncated: showing ${shown} of ${total} characters. Narrow your query (e.g. add 'type' or reduce 'limit') to see more._`;
}

function capText(text: string): string {
  if (text.length <= CHARACTER_LIMIT) return text;
  return text.slice(0, CHARACTER_LIMIT) + truncateNote(CHARACTER_LIMIT, text.length);
}

export function registerHealthTools(server: McpServer): void {
  // ---------------------------------------------------------------------
  // health_connect
  // ---------------------------------------------------------------------
  const ConnectInputSchema = z
    .object({
      provider: z
        .enum(HEALTH_PROVIDERS)
        .describe(`Health data provider to connect. One of: ${HEALTH_PROVIDERS.join(", ")}`),
    })
    .strict();

  server.registerTool(
    "health_connect",
    {
      title: "Connect Health Provider",
      description: `Record which health data provider the locally-imported records come from.

This does NOT establish live device access — Apple HealthKit and Google Health Connect are on-device SDKs with no server-reachable API, so this tool cannot pull data automatically. It only records the active provider so that ` +
        "`health_import_records`" +
        ` knows how to label records you import from a JSON export.

Args:
  - provider ('apple_health' | 'google_health_connect'): the provider the exported data comes from

Returns:
  Confirmation text and structured data: { "provider": string, "connectedAt": string (ISO date) }

Examples:
  - Use when: "Connect my Apple Health data" -> params with provider="apple_health"
  - Don't use when: you just want to see current status (use health_status instead)

Error Handling:
  - Rejects any provider not in the supported list, listing the valid options`,
      inputSchema: ConnectInputSchema,
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ provider }) => {
      const state = loadState();
      state.healthConnection = { provider, connectedAt: new Date().toISOString() };
      saveState(state);
      const output = { provider, connectedAt: state.healthConnection.connectedAt };
      return {
        content: [
          {
            type: "text",
            text:
              `Connected to ${provider}.\n` +
              `Export your data from the provider's app and import it with health_import_records.`,
          },
        ],
        structuredContent: output,
      };
    },
  );

  // ---------------------------------------------------------------------
  // health_disconnect
  // ---------------------------------------------------------------------
  server.registerTool(
    "health_disconnect",
    {
      title: "Disconnect Health Provider",
      description: `Clear the locally recorded health provider connection. Does not delete previously imported records.

Args: (none)

Returns:
  Confirmation text and structured data: { "wasConnected": boolean }

Examples:
  - Use when: "Disconnect my health provider" -> no params needed`,
      inputSchema: z.object({}).strict(),
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async () => {
      const state = loadState();
      const wasConnected = state.healthConnection !== null;
      state.healthConnection = null;
      saveState(state);
      return {
        content: [{ type: "text", text: wasConnected ? "Disconnected." : "No health provider was connected." }],
        structuredContent: { wasConnected },
      };
    },
  );

  // ---------------------------------------------------------------------
  // health_status
  // ---------------------------------------------------------------------
  const StatusInputSchema = z.object({ response_format: ResponseFormatSchema }).strict();

  server.registerTool(
    "health_status",
    {
      title: "Get Health Connection Status",
      description: `Show the currently connected health provider and how many records are stored locally.

Args:
  - response_format ('markdown' | 'json'): output format (default: 'markdown')

Returns:
  For JSON format: { "connected": boolean, "provider": string | null, "connectedAt": string | null, "recordCount": number }

Examples:
  - Use when: "Is my health data connected?" -> no other params needed`,
      inputSchema: StatusInputSchema,
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ response_format }) => {
      const state = loadState();
      const output = {
        connected: state.healthConnection !== null,
        provider: state.healthConnection?.provider ?? null,
        connectedAt: state.healthConnection?.connectedAt ?? null,
        recordCount: state.healthRecords.length,
      };

      let text: string;
      if (response_format === ResponseFormat.JSON) {
        text = JSON.stringify(output, null, 2);
      } else if (!output.connected) {
        text = "Not connected. Use health_connect to record a provider first.";
      } else {
        text =
          `# Health Status\n\n` +
          `- **Provider**: ${output.provider}\n` +
          `- **Connected**: ${output.connectedAt}\n` +
          `- **Records stored**: ${output.recordCount}`;
      }

      return { content: [{ type: "text", text }], structuredContent: output };
    },
  );

  // ---------------------------------------------------------------------
  // health_import_records
  // ---------------------------------------------------------------------
  const InlineRecordSchema = z.object({
    type: z.string().min(1).describe("Metric type, e.g. 'steps', 'heart_rate', 'sleep_minutes', 'weight_kg'"),
    value: z.number().describe("Numeric measurement value"),
    unit: z.string().min(1).describe("Unit for the value, e.g. 'count', 'bpm', 'kg'"),
    recordedAt: z
      .string()
      .refine((v) => !Number.isNaN(Date.parse(v)), "must be a valid ISO 8601 date string")
      .describe("ISO 8601 timestamp when the measurement was taken"),
  });

  const ImportInputSchema = z
    .object({
      file_path: z
        .string()
        .min(1)
        .optional()
        .describe(
          'Absolute path to a local JSON export file shaped as { "records": [{ type, value, unit, recordedAt }] }. Mutually exclusive with "records".',
        ),
      records: z
        .array(InlineRecordSchema)
        .min(1)
        .optional()
        .describe("Records to import directly, when you already have them in hand instead of a file. Mutually exclusive with \"file_path\"."),
    })
    .strict()
    .refine((v) => (v.file_path ? 1 : 0) + (v.records ? 1 : 0) === 1, {
      message: 'Provide exactly one of "file_path" or "records", not both and not neither.',
    });

  server.registerTool(
    "health_import_records",
    {
      title: "Import Health Records",
      description: `Import health measurements into local storage, either from a JSON export file or from an inline records array.

Requires an active connection (call health_connect first) — imported records are tagged with the currently connected provider as their source.

Args:
  - file_path (string, optional): path to a JSON file shaped as { "records": [{ type, value, unit, recordedAt }] }
  - records (array, optional): records to import directly, each with { type, value, unit, recordedAt }
  - Exactly one of file_path or records must be given.

Returns:
  Confirmation text and structured data: { "imported": number, "provider": string }

Examples:
  - Use when: "Import my exported Apple Health data from ~/Downloads/export.json" -> params with file_path="~/Downloads/export.json"
  - Use when: an agent already parsed records itself and wants to store them -> params with records=[{...}]
  - Don't use when: no provider is connected yet (call health_connect first)

Error Handling:
  - Returns "Error: no provider connected..." if health_connect has not been called
  - Returns "Error: could not read file..." if file_path does not exist or is unreadable
  - Returns "Error: <file> is not valid JSON." if the file cannot be parsed
  - Returns a specific validation message naming the bad field/index if a record is malformed`,
      inputSchema: ImportInputSchema,
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: false,
      },
    },
    async ({ file_path, records }) => {
      const state = loadState();
      if (!state.healthConnection) {
        return {
          isError: true,
          content: [{ type: "text", text: "Error: no provider connected. Call health_connect first." }],
        };
      }

      let entries: ParsedHealthEntry[];
      if (records) {
        entries = records;
      } else {
        let raw: string;
        try {
          raw = readFileSync(file_path!, "utf-8");
        } catch {
          return {
            isError: true,
            content: [{ type: "text", text: `Error: could not read file "${file_path}".` }],
          };
        }
        let data: unknown;
        try {
          data = JSON.parse(raw);
        } catch {
          return {
            isError: true,
            content: [{ type: "text", text: `Error: "${file_path}" is not valid JSON.` }],
          };
        }
        try {
          entries = parseHealthEntries(data);
        } catch (err) {
          return {
            isError: true,
            content: [{ type: "text", text: `Error: ${err instanceof Error ? err.message : String(err)}` }],
          };
        }
      }

      const importedAt = new Date().toISOString();
      const provider = state.healthConnection.provider;
      const newRecords: HealthRecord[] = entries.map((entry) => ({
        id: newRecordId(),
        ...entry,
        source: provider,
        importedAt,
      }));
      state.healthRecords.push(...newRecords);
      saveState(state);

      const output = { imported: newRecords.length, provider };
      return {
        content: [{ type: "text", text: `Imported ${newRecords.length} record(s) from ${provider}.` }],
        structuredContent: output,
      };
    },
  );

  // ---------------------------------------------------------------------
  // health_list_records
  // ---------------------------------------------------------------------
  const ListInputSchema = z
    .object({
      type: z.string().min(1).optional().describe("Filter to records of this metric type only, e.g. 'steps'"),
      limit: z
        .number()
        .int()
        .min(1)
        .max(MAX_LIST_LIMIT)
        .default(DEFAULT_LIST_LIMIT)
        .describe(`Maximum records to return (default ${DEFAULT_LIST_LIMIT}, max ${MAX_LIST_LIMIT})`),
      offset: z.number().int().min(0).default(0).describe("Number of records to skip, for pagination"),
      response_format: ResponseFormatSchema,
    })
    .strict();

  server.registerTool(
    "health_list_records",
    {
      title: "List Health Records",
      description: `List imported health records, most recent first, with optional type filtering and pagination.

Args:
  - type (string, optional): filter to a single metric type, e.g. 'steps'
  - limit (number): max records to return, 1-${MAX_LIST_LIMIT} (default ${DEFAULT_LIST_LIMIT})
  - offset (number): records to skip for pagination (default 0)
  - response_format ('markdown' | 'json'): output format (default: 'markdown')

Returns:
  For JSON format: { "total": number, "count": number, "offset": number, "records": [...], "has_more": boolean, "next_offset"?: number }

Examples:
  - Use when: "Show my last 10 step readings" -> params with type="steps", limit=10
  - Use when: "List everything imported" -> no params needed (defaults apply)

Error Handling:
  - Returns an empty list (not an error) if no records match the filter`,
      inputSchema: ListInputSchema,
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ type, limit, offset, response_format }) => {
      const state = loadState();
      const filtered = type ? state.healthRecords.filter((r) => r.type === type) : state.healthRecords;
      const sorted = [...filtered].sort((a, b) => b.recordedAt.localeCompare(a.recordedAt));
      const page = sorted.slice(offset, offset + limit);
      const hasMore = offset + page.length < sorted.length;

      const output = {
        total: sorted.length,
        count: page.length,
        offset,
        records: page,
        has_more: hasMore,
        ...(hasMore ? { next_offset: offset + page.length } : {}),
      };

      let text: string;
      if (response_format === ResponseFormat.JSON) {
        text = JSON.stringify(output, null, 2);
      } else if (page.length === 0) {
        text = type ? `No records found for type "${type}".` : "No records imported yet.";
      } else {
        const lines = [`# Health Records (${output.count} of ${output.total})`, ""];
        for (const r of page) {
          lines.push(`- **${r.type}**: ${r.value} ${r.unit} — ${r.recordedAt} (${r.source})`);
        }
        if (hasMore) {
          lines.push("", `_More available — call again with offset=${output.next_offset}._`);
        }
        text = lines.join("\n");
      }

      return { content: [{ type: "text", text: capText(text) }], structuredContent: output };
    },
  );

  // ---------------------------------------------------------------------
  // health_summary
  // ---------------------------------------------------------------------
  const SummaryInputSchema = z
    .object({
      type: z.string().min(1).optional().describe("Restrict the summary to a single metric type, e.g. 'steps'"),
      response_format: ResponseFormatSchema,
    })
    .strict();

  server.registerTool(
    "health_summary",
    {
      title: "Summarize Health Records",
      description: `Compute aggregate stats (count, min, max, average, latest value) per metric type across imported records.

Args:
  - type (string, optional): restrict the summary to one metric type
  - response_format ('markdown' | 'json'): output format (default: 'markdown')

Returns:
  For JSON format: { "summaries": [{ type, count, unit, latestValue, latestAt, min, max, avg }] }

Examples:
  - Use when: "What's my average heart rate from imported data?" -> params with type="heart_rate"
  - Use when: "Summarize everything I've imported" -> no params needed`,
      inputSchema: SummaryInputSchema,
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ type, response_format }) => {
      const state = loadState();
      const records = type ? state.healthRecords.filter((r) => r.type === type) : state.healthRecords;
      const summaries = summarizeHealthRecords(records);
      const output = { summaries };

      let text: string;
      if (response_format === ResponseFormat.JSON) {
        text = JSON.stringify(output, null, 2);
      } else if (summaries.length === 0) {
        text = type ? `No records found for type "${type}".` : "No records imported yet.";
      } else {
        const lines = ["# Health Summary", ""];
        for (const s of summaries) {
          lines.push(
            `## ${s.type}`,
            `- count: ${s.count}`,
            `- latest: ${s.latestValue} ${s.unit} (${s.latestAt})`,
            `- min / avg / max: ${s.min} / ${s.avg.toFixed(2)} / ${s.max}`,
            "",
          );
        }
        text = lines.join("\n");
      }

      return { content: [{ type: "text", text: capText(text) }], structuredContent: output };
    },
  );
}
