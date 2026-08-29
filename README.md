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

-- Apple Health import (see "Import Apple Health data" below). Requires
-- pgcrypto for gen_random_uuid() — enabled by default on Supabase; if it
-- errors, run `create extension if not exists pgcrypto;` first.
create table if not exists public.health_records (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  type        text not null,
  source_name text,
  unit        text,
  value       text not null,
  start_date  timestamptz not null,
  end_date    timestamptz not null,
  created_at  timestamptz not null default now()
);
create index if not exists health_records_user_type_idx on public.health_records(user_id, type);
create index if not exists health_records_start_date_idx on public.health_records(start_date);
alter table public.health_records enable row level security;
create policy "health_records_select_own" on public.health_records for select using (auth.uid() = user_id);
create policy "health_records_insert_own" on public.health_records for insert with check (auth.uid() = user_id);
create policy "health_records_delete_own" on public.health_records for delete using (auth.uid() = user_id);

-- Backs `claude-console health summary`. security invoker (the default)
-- means it runs as the calling user, so RLS already scopes it to their
-- own rows — the explicit where clause is just defensive.
create or replace function public.health_summary()
returns table(type text, count bigint, first_date timestamptz, last_date timestamptz)
language sql
security invoker
as $$
  select type, count(*), min(start_date), max(start_date)
  from public.health_records
  where user_id = auth.uid()
  group by type
  order by type;
$$;
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

claude-console health import <file>
claude-console health summary
claude-console health list [--type <type>] [--since <date>] [--limit <n>]
```

`auth login`/`auth signup` take the password as a plain CLI argument for
simplicity — note that this puts it in your shell history.

## Import Apple Health data

HealthKit only exposes data on-device — there's no cloud API a CLI can call
directly — so this works from a manual export instead:

1. On your iPhone: Health app → tap your profile picture → **Export All
   Health Data** → this produces `export.zip`.
2. Get it onto the machine running the CLI (AirDrop, Files app, email to
   yourself, etc.) and unzip it — it contains `apple_health_export/export.xml`.
3. Run:
   ```sh
   claude-console health import path/to/apple_health_export/export.xml
   ```

This streams the XML (exports can be large) and uploads every `<Record>`
element — steps, heart rate, workouts' quantity samples, etc. — to your
`health_records` table in batches of 500, scoped to your logged-in user via
RLS. Records missing a type/value/date, or with a date that fails to parse,
are silently skipped and counted. `Workout`, `Correlation`, and
`ClinicalRecord` elements aren't imported yet — only generic `Record`s.

`health summary` shows counts and date ranges per record type;
`health list` shows the raw rows, optionally filtered by `--type` (e.g.
`HKQuantityTypeIdentifierStepCount`) or `--since` an ISO date.

## Development

```sh
npm run typecheck
npm test
```

Unit tests cover local state caching (`test/local.test.ts`), the Supabase
row mappers / config resolution (`test/store.test.ts`), and the Apple
Health XML parser against a synthetic fixture (`test/health.test.ts`) —
all offline. Anything that talks to a live Supabase project (login, CRUD,
RLS enforcement, an actual health import) needs to be smoke-tested against
your own project; it isn't covered by the automated suite.

Set `CLAUDE_CONSOLE_HOME` to override where local state is stored (used by
the test suite to avoid touching your real `~/.claude-console`).
