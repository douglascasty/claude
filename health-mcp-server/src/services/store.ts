import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { randomUUID } from "node:crypto";
import type { StoreState } from "../types.js";

function stateDir(): string {
  return process.env.CLAUDE_CONSOLE_HOME ?? join(homedir(), ".claude-console");
}

function stateFile(): string {
  return join(stateDir(), "state.json");
}

function emptyState(): StoreState {
  return { healthConnection: null, healthRecords: [] };
}

export function loadState(): StoreState {
  const file = stateFile();
  if (!existsSync(file)) {
    return emptyState();
  }
  try {
    const raw = readFileSync(file, "utf-8");
    return { ...emptyState(), ...JSON.parse(raw) };
  } catch {
    return emptyState();
  }
}

export function saveState(state: StoreState): void {
  const dir = stateDir();
  if (!existsSync(dir)) {
    mkdirSync(dir, { recursive: true });
  }
  writeFileSync(stateFile(), JSON.stringify(state, null, 2), "utf-8");
}

export function newRecordId(): string {
  return `hrec_${randomUUID().replace(/-/g, "").slice(0, 12)}`;
}
