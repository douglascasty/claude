import { describe, expect, it, beforeEach, afterEach } from "vitest";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { loadState, saveState, newId } from "../src/lib/local.js";

let tmpHome: string;
let originalHome: string | undefined;

beforeEach(() => {
  tmpHome = mkdtempSync(join(tmpdir(), "claude-console-test-"));
  originalHome = process.env.CLAUDE_CONSOLE_HOME;
  process.env.CLAUDE_CONSOLE_HOME = tmpHome;
});

afterEach(() => {
  process.env.CLAUDE_CONSOLE_HOME = originalHome;
  rmSync(tmpHome, { recursive: true, force: true });
});

describe("local state", () => {
  it("returns empty state when nothing is persisted yet", () => {
    const state = loadState();
    expect(state.session).toBeNull();
    expect(state.config).toEqual({});
  });

  it("round-trips saved state", () => {
    const state = loadState();
    state.config.supabase_url = "https://example.supabase.co";
    state.session = {
      email: "dev@example.com",
      userId: "user-1",
      accessToken: "access-token",
      refreshToken: "refresh-token",
      expiresAt: 1234567890,
    };
    saveState(state);

    const reloaded = loadState();
    expect(reloaded.config.supabase_url).toBe("https://example.supabase.co");
    expect(reloaded.session?.email).toBe("dev@example.com");
    expect(reloaded.session?.userId).toBe("user-1");
  });

  it("generates ids with the given prefix", () => {
    expect(newId("proj")).toMatch(/^proj_[a-f0-9]{12}$/);
  });
});
