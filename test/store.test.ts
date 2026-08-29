import { describe, expect, it, beforeEach, afterEach } from "vitest";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { loadState, saveState, newId } from "../src/lib/store.js";

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

describe("store", () => {
  it("returns empty state when nothing is persisted yet", () => {
    const state = loadState();
    expect(state.session).toBeNull();
    expect(state.projects).toEqual([]);
    expect(state.apiKeys).toEqual([]);
  });

  it("round-trips saved state", () => {
    const state = loadState();
    const project = { id: newId("proj"), name: "demo", createdAt: new Date().toISOString() };
    state.projects.push(project);
    saveState(state);

    const reloaded = loadState();
    expect(reloaded.projects).toHaveLength(1);
    expect(reloaded.projects[0].name).toBe("demo");
  });

  it("generates ids with the given prefix", () => {
    expect(newId("proj")).toMatch(/^proj_[a-f0-9]{12}$/);
  });
});
