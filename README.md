# claude-console

A CLI for the Claude Code Console developer platform: manage your session,
projects, and API keys from the terminal.

## Status

This is a starter scaffold. State (session, projects, API keys) is persisted
locally to `~/.claude-console/state.json` — there is no backend API wired up
yet. The command surface and local data model are built so a real HTTP
client can be dropped in behind `src/lib/store.ts` later without changing
the CLI commands themselves.

## Install

```sh
npm install
npm run build
npm link   # exposes the `claude-console` command globally
```

Or run it directly during development:

```sh
npm run dev -- <command> [args]
```

## Commands

```sh
claude-console auth login <email>
claude-console auth whoami
claude-console auth logout

claude-console config set <key> <value>
claude-console config get <key>
claude-console config list
claude-console config unset <key>

claude-console projects create <name>
claude-console projects list
claude-console projects show <id>
claude-console projects delete <id>

claude-console keys create <projectId> [--name <name>]
claude-console keys list <projectId>
claude-console keys revoke <keyId>

claude-console usage <projectId>

claude-console health connect <provider>   # apple_health | google_health_connect
claude-console health status
claude-console health import <file>        # JSON: { "records": [{ type, value, unit, recordedAt }] }
claude-console health list [--type <type>] [--limit <n>]
claude-console health summary
claude-console health disconnect
```

The `health` commands have no device-level access to HealthKit or Health
Connect — those are on-device SDKs, not something a terminal process can
reach. Export your data from the provider's app into the JSON shape above
and import it locally; the connection step just records which provider the
imported data came from.

## Development

```sh
npm run typecheck
npm test
```

Set `CLAUDE_CONSOLE_HOME` to override where local state is stored (used by
the test suite to avoid touching your real `~/.claude-console`).

## MCP server

[`health-mcp-server/`](./health-mcp-server) exposes the same health-data
connector as MCP tools (`health_connect`, `health_import_records`,
`health_list_records`, `health_summary`, ...) so an agent can drive it
directly instead of shelling out to `claude-console health ...`. It reads
and writes the same local state file, so data imported through either one
is visible to the other. See its own README for setup and tool docs.
