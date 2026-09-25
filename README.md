# claude-console

`claude-console` is an open-source TypeScript CLI for experimenting with a
Supabase-backed developer project registry. It provides local configuration,
email-based authentication through Supabase, and project CRUD commands.

The project is independent and is not affiliated with or endorsed by Anthropic,
OpenAI, or Supabase.

## What works today

- Create an account and sign in to a Supabase project you control.
- Create, list, inspect, and delete projects with row-level access controls.
- Keep CLI configuration and the Supabase session in a local file with
  owner-only permissions where supported.

Credential and API-key management are deliberately disabled. The project will
not store raw API keys until it has a reviewed secure-storage design.

## Quick start

Requires Node.js 20 or later.

```sh
npm install
npm run build
npm link
```

Create a Supabase project, then set its public URL and anon key. Never use a
service-role key with this CLI.

```sh
export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_ANON_KEY="your-anon-key"
claude-console auth signup you@example.com
claude-console projects create "example"
claude-console projects list
```

## Supabase setup

Run this SQL in the Supabase SQL editor before using project commands:

```sql
create table if not exists public.projects (
  id text primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  name text not null,
  created_at timestamptz not null default now()
);
alter table public.projects enable row level security;
create policy "projects_select_own" on public.projects for select using (auth.uid() = user_id);
create policy "projects_insert_own" on public.projects for insert with check (auth.uid() = user_id);
create policy "projects_update_own" on public.projects for update using (auth.uid() = user_id);
create policy "projects_delete_own" on public.projects for delete using (auth.uid() = user_id);
```

## Commands

```text
claude-console auth signup <email>
claude-console auth login <email>
claude-console auth whoami
claude-console auth logout
claude-console config set <key> <value>
claude-console projects create <name>
claude-console projects list
claude-console projects show <id>
claude-console projects delete <id>
```

Passwords are read from an interactive prompt without echo, or from the first
line of stdin when it is not a terminal. They are never taken as arguments.

## Development

```sh
npm run typecheck
npm test
```

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and
[ROADMAP.md](ROADMAP.md).

## License

Licensed under [Apache-2.0](LICENSE).
