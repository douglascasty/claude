# health-mcp-server

An MCP server that lets an agent connect a health data provider, import
exported records, and query/summarize them.

## Status

Apple HealthKit and Google Health Connect are on-device SDKs with no
server-reachable API — there is no way for a process like this to pull data
from them directly. `health_connect` just records which provider your data
comes from; `health_import_records` ingests records you've already exported
to JSON (or that an agent has parsed itself) into local storage.

State is persisted to `~/.claude-console/state.json` (override with
`CLAUDE_CONSOLE_HOME`) — the same file used by the sibling `claude-console`
CLI's `health` command, so data imported through either one is visible to
the other.

## Tools

| Tool | Description |
| --- | --- |
| `health_connect` | Record the active provider (`apple_health` or `google_health_connect`) |
| `health_disconnect` | Clear the active provider |
| `health_status` | Show connection state and stored record count |
| `health_import_records` | Import records from a JSON file (`file_path`) or inline (`records`) |
| `health_list_records` | List records, paginated, optionally filtered by `type` |
| `health_summary` | Aggregate stats (count/min/max/avg/latest) per record type |

Each list/summary/status tool accepts `response_format: "markdown" | "json"`.

### Import file shape

```json
{
  "records": [
    { "type": "steps", "value": 8123, "unit": "count", "recordedAt": "2026-08-28T10:00:00Z" },
    { "type": "heart_rate", "value": 62, "unit": "bpm", "recordedAt": "2026-08-28T09:00:00Z" }
  ]
}
```

## Install & build

```sh
npm install
npm run build
```

## Run

```sh
npm start
# or during development:
npm run dev
```

The server speaks MCP over stdio.

## Register with an MCP client

Add to your client's MCP config (e.g. `.mcp.json` for Claude Code):

```json
{
  "mcpServers": {
    "health": {
      "command": "node",
      "args": ["/absolute/path/to/health-mcp-server/dist/index.js"]
    }
  }
}
```

## Development

```sh
npm run typecheck
npm test
```
