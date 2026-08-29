import { Command } from "commander";
import { randomBytes } from "node:crypto";
import { getProject, listApiKeys, getApiKey, createApiKey, revokeApiKey } from "../lib/store.js";
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
    .action(async (projectId: string, opts: { name: string }) => {
      const project = await getProject(projectId);
      if (!project) {
        fail(`no project found with id "${projectId}"`);
      }
      const key = await createApiKey(projectId, opts.name, generateToken());
      console.log(`Created key "${key.name}" for ${project.name}.`);
      console.log(`Token (shown once): ${key.token}`);
    });

  keys
    .command("list")
    .description("list API keys for a project")
    .argument("<projectId>", "project id")
    .action(async (projectId: string) => {
      const all = await listApiKeys(projectId);
      printTable(
        all.map((k) => ({
          id: k.id,
          name: k.name,
          status: k.revokedAt ? "revoked" : "active",
          created: k.createdAt,
        })),
      );
    });

  keys
    .command("revoke")
    .description("revoke an API key")
    .argument("<keyId>", "key id")
    .action(async (keyId: string) => {
      const key = await getApiKey(keyId);
      if (!key) {
        fail(`no key found with id "${keyId}"`);
      }
      if (key.revokedAt) {
        console.log(`Key ${keyId} is already revoked.`);
        return;
      }
      await revokeApiKey(keyId);
      console.log(`Revoked key ${keyId}.`);
    });
}
