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
```

## Development

```sh
npm run typecheck
npm test
```

Set `CLAUDE_CONSOLE_HOME` to override where local state is stored (used by
the test suite to avoid touching your real `~/.claude-console`).
