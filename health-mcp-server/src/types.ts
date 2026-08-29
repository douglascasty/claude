export type HealthProvider = "apple_health" | "google_health_connect";

export interface HealthConnection {
  provider: HealthProvider;
  connectedAt: string;
}

export interface HealthRecord {
  id: string;
  type: string;
  value: number;
  unit: string;
  recordedAt: string;
  source: HealthProvider;
  importedAt: string;
}

export interface ParsedHealthEntry {
  type: string;
  value: number;
  unit: string;
  recordedAt: string;
}

/**
 * The on-disk state shape. Extends beyond health fields because this file is
 * shared with the sibling `claude-console` CLI (same CLAUDE_CONSOLE_HOME
 * directory) — unknown fields written by the CLI (session, config, projects,
 * apiKeys, ...) are round-tripped untouched via the index signature.
 */
export interface StoreState {
  healthConnection: HealthConnection | null;
  healthRecords: HealthRecord[];
  [key: string]: unknown;
}
