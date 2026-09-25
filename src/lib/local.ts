import { chmodSync, existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { randomUUID } from "node:crypto";

export interface Session {
  email: string;
  userId: string;
  accessToken: string;
  refreshToken: string;
  expiresAt: number | null;
}

export interface State {
  session: Session | null;
  config: Record<string, string>;
}

function stateDir(): string {
  return process.env.CLAUDE_CONSOLE_HOME ?? join(homedir(), ".claude-console");
}

function stateFile(): string {
  return join(stateDir(), "state.json");
}

function emptyState(): State {
  return { session: null, config: {} };
}

export function loadState(): State {
  const file = stateFile();
  if (!existsSync(file)) {
    return emptyState();
  }
  const raw = readFileSync(file, "utf-8");
  try {
    return { ...emptyState(), ...JSON.parse(raw) };
  } catch {
    // Keep a copy so the next save doesn't silently destroy the user's data.
    const backup = `${file}.corrupt-${Date.now()}`;
    writeFileSync(backup, raw, { encoding: "utf-8", mode: 0o600 });
    console.error(`Warning: ${file} is not valid JSON; backed up to ${backup} and starting fresh.`);
    return emptyState();
  }
}

export function saveState(state: State): void {
  const dir = stateDir();
  if (!existsSync(dir)) {
    mkdirSync(dir, { recursive: true, mode: 0o700 });
  }
  // `mode` only applies on creation, so tighten pre-existing paths explicitly.
  chmodSync(dir, 0o700);
  const file = stateFile();
  const tmp = `${file}.${process.pid}.tmp`;
  writeFileSync(tmp, JSON.stringify(state, null, 2), { encoding: "utf-8", mode: 0o600 });
  chmodSync(tmp, 0o600);
  renameSync(tmp, file);
}

export function newId(prefix: string): string {
  return `${prefix}_${randomUUID().replace(/-/g, "").slice(0, 12)}`;
}

export function stateFilePath(): string {
  return stateFile();
}
