import { Command } from "commander";
import { randomBytes } from "node:crypto";
import { loadState, saveState, newId } from "../lib/store.js";
import { printTable, fail } from "../lib/output.js";

function generateToken(): string {
  return `sk-console-${randomBytes(18).toString("hex")}`;
}

export function registerKeyCommands(program: Command): void {
  const keys = program.command("keys").description("manage project API keys");

  keys
    .command("create")
    .description("create a new API key for a project")
    .argument("<projectId>", "project id")
    .option("-n, --name <name>", "key name", "default")
    .action((projectId: string, opts: { name: string }) => {
      const state = loadState();
      const project = state.projects.find((p) => p.id === projectId);
      if (!project) {
        fail(`no project found with id "${projectId}"`);
      }
      const key = {
        id: newId("key"),
        name: opts.name,
        projectId,
        token: generateToken(),
        createdAt: new Date().toISOString(),
        revokedAt: null as string | null,
      };
      state.apiKeys.push(key);
      saveState(state);
      console.log(`Created key "${key.name}" for ${project.name}.`);
      console.log(`Token (shown once): ${key.token}`);
    });

  keys
    .command("list")
    .description("list API keys for a project")
    .argument("<projectId>", "project id")
    .action((projectId: string) => {
      const state = loadState();
      const rows = state.apiKeys
        .filter((k) => k.projectId === projectId)
        .map((k) => ({
          id: k.id,
          name: k.name,
          status: k.revokedAt ? "revoked" : "active",
          created: k.createdAt,
        }));
      printTable(rows);
    });

  keys
    .command("revoke")
    .description("revoke an API key")
    .argument("<keyId>", "key id")
    .action((keyId: string) => {
      const state = loadState();
      const key = state.apiKeys.find((k) => k.id === keyId);
      if (!key) {
        fail(`no key found with id "${keyId}"`);
      }
      if (key.revokedAt) {
        console.log(`Key ${keyId} is already revoked.`);
        return;
      }
      key.revokedAt = new Date().toISOString();
      saveState(state);
      console.log(`Revoked key ${keyId}.`);
    });
}
