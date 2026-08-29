# claude-console

A CLI for the Claude Code Console developer platform: manage your session,
projects, and API keys from the terminal, backed by a real Supabase
(Postgres + Auth) project.

## Status

Auth, projects, and API keys are persisted in your own Supabase project via
`@supabase/supabase-js` — this CLI talks to Supabase directly over HTTP, not
through any Claude/MCP connector, so it works standalone for any user. Only
your session cache and CLI config (the Supabase URL/key you point it at)
stay local, in `~/.claude-console/state.json`.

## Set up your Supabase project

1. Create a project at [supabase.com](https://supabase.com) (or self-host).
   Get the **Project URL** and **anon public key** from Settings → API.
2. In Authentication → Providers → Email, decide whether to require email
   confirmation. Leave it on for production; turn it off if you want
   `auth signup` to log you in immediately while testing.
3. Run this in the SQL Editor:

```sql
create table if not exists public.projects (
  id         text primary key,
  user_id    uuid not null references auth.users(id) on delete cascade,
  name       text not null,
  created_at timestamptz not null default now()
);
alter table public.projects enable row level security;
create policy "projects_select_own" on public.projects for select using (auth.uid() = user_id);
create policy "projects_insert_own" on public.projects for insert with check (auth.uid() = user_id);
create policy "projects_update_own" on public.projects for update using (auth.uid() = user_id);
create policy "projects_delete_own" on public.projects for delete using (auth.uid() = user_id);

create table if not exists public.api_keys (
  id          text primary key,
  user_id     uuid not null references auth.users(id) on delete cascade,
  project_id  text not null references public.projects(id) on delete cascade,
  name        text not null,
  token       text not null,
  created_at  timestamptz not null default now(),
  revoked_at  timestamptz
);
create index if not exists api_keys_project_id_idx on public.api_keys(project_id);
alter table public.api_keys enable row level security;
create policy "api_keys_select_own" on public.api_keys for select using (auth.uid() = user_id);
create policy "api_keys_insert_own" on public.api_keys for insert with check (auth.uid() = user_id);
create policy "api_keys_update_own" on public.api_keys for update using (auth.uid() = user_id);
create policy "api_keys_delete_own" on public.api_keys for delete using (auth.uid() = user_id);
```

Row Level Security means every user only ever sees their own projects and
keys — `auth.uid()` is resolved from the session token the CLI attaches to
each request.

API key tokens are stored in plaintext in `api_keys.token`, same as before —
hashing them is a known future hardening item, not handled by this CLI yet.

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

## Configure

```sh
claude-console config set supabase_url <your-project-url>
claude-console config set supabase_anon_key <your-anon-key>
```

Or set `SUPABASE_URL` / `SUPABASE_ANON_KEY` environment variables instead —
these take precedence over the config values, which is useful for CI or
non-interactive use.

## Commands

```sh
claude-console auth signup <email> <password>
claude-console auth login <email> <password>
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

`auth login`/`auth signup` take the password as a plain CLI argument for
simplicity — note that this puts it in your shell history.

## Development

```sh
npm run typecheck
npm test
```

Unit tests cover local state caching (`test/local.test.ts`) and the
Supabase row mappers / config resolution (`test/store.test.ts`) — all
offline. Anything that talks to a live Supabase project (login, CRUD,
RLS enforcement) needs to be smoke-tested against your own project; it
isn't covered by the automated suite.

Set `CLAUDE_CONSOLE_HOME` to override where local state is stored (used by
the test suite to avoid touching your real `~/.claude-console`).
