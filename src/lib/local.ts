import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
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
  try {
    const raw = readFileSync(file, "utf-8");
    return { ...emptyState(), ...JSON.parse(raw) };
  } catch {
    return emptyState();
  }
}

export function saveState(state: State): void {
  const dir = stateDir();
  if (!existsSync(dir)) {
    mkdirSync(dir, { recursive: true, mode: 0o700 });
  }
  writeFileSync(stateFile(), JSON.stringify(state, null, 2), { encoding: "utf-8", mode: 0o600 });
}

export function newId(prefix: string): string {
  return `${prefix}_${randomUUID().replace(/-/g, "").slice(0, 12)}`;
}

export function stateFilePath(): string {
  return stateFile();
}
