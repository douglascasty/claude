import { describe, expect, it, beforeEach, afterEach } from "vitest";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { mapProject, mapApiKey } from "../src/lib/store.js";
import { saveState, loadState } from "../src/lib/local.js";
import { resolveSupabaseConfig } from "../src/lib/supabase.js";

describe("row mappers", () => {
  it("maps a project row to camelCase", () => {
    const project = mapProject({ id: "proj_abc123", name: "demo", created_at: "2026-01-01T00:00:00Z" });
    expect(project).toEqual({ id: "proj_abc123", name: "demo", createdAt: "2026-01-01T00:00:00Z" });
  });

  it("maps an api_key row to camelCase", () => {
    const key = mapApiKey({
      id: "key_abc123",
      name: "ci",
      project_id: "proj_abc123",
      token: "sk-console-xyz",
      created_at: "2026-01-01T00:00:00Z",
      revoked_at: null,
    });
    expect(key).toEqual({
      id: "key_abc123",
      name: "ci",
      projectId: "proj_abc123",
      token: "sk-console-xyz",
      createdAt: "2026-01-01T00:00:00Z",
      revokedAt: null,
    });
  });
});

describe("resolveSupabaseConfig", () => {
  let tmpHome: string;
  let originalHome: string | undefined;
  let originalUrl: string | undefined;
  let originalKey: string | undefined;

  beforeEach(() => {
    tmpHome = mkdtempSync(join(tmpdir(), "claude-console-test-"));
    originalHome = process.env.CLAUDE_CONSOLE_HOME;
    originalUrl = process.env.SUPABASE_URL;
    originalKey = process.env.SUPABASE_ANON_KEY;
    process.env.CLAUDE_CONSOLE_HOME = tmpHome;
    delete process.env.SUPABASE_URL;
    delete process.env.SUPABASE_ANON_KEY;
  });

  afterEach(() => {
    process.env.CLAUDE_CONSOLE_HOME = originalHome;
    if (originalUrl === undefined) delete process.env.SUPABASE_URL;
    else process.env.SUPABASE_URL = originalUrl;
    if (originalKey === undefined) delete process.env.SUPABASE_ANON_KEY;
    else process.env.SUPABASE_ANON_KEY = originalKey;
    rmSync(tmpHome, { recursive: true, force: true });
  });

  it("reads from local config when no env vars are set", () => {
    const state = loadState();
    state.config.supabase_url = "https://from-config.supabase.co";
    state.config.supabase_anon_key = "config-key";
    saveState(state);

    expect(resolveSupabaseConfig()).toEqual({
      url: "https://from-config.supabase.co",
      anonKey: "config-key",
    });
  });

  it("prefers env vars over local config", () => {
    const state = loadState();
    state.config.supabase_url = "https://from-config.supabase.co";
    state.config.supabase_anon_key = "config-key";
    saveState(state);

    process.env.SUPABASE_URL = "https://from-env.supabase.co";
    process.env.SUPABASE_ANON_KEY = "env-key";

    expect(resolveSupabaseConfig()).toEqual({
      url: "https://from-env.supabase.co",
      anonKey: "env-key",
    });
  });
});
