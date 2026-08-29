import { Command } from "commander";
import { loadState } from "../lib/store.js";
import { fail } from "../lib/output.js";

export function registerUsageCommands(program: Command): void {
  program
    .command("usage")
    .description("show local API key activity for a project")
    .argument("<projectId>", "project id")
    .action((projectId: string) => {
      const state = loadState();
      const project = state.projects.find((p) => p.id === projectId);
      if (!project) {
        fail(`no project found with id "${projectId}"`);
      }
      const keys = state.apiKeys.filter((k) => k.projectId === projectId);
      const active = keys.filter((k) => !k.revokedAt).length;
      const revoked = keys.length - active;

      console.log(`Project: ${project.name} (${project.id})`);
      console.log(`Keys:    ${keys.length} total, ${active} active, ${revoked} revoked`);
      console.log();
      console.log(
        "Note: request-level usage metrics require a Console API endpoint, which " +
          'this CLI does not yet talk to. Set one with `claude-console config set api_url <url>` ' +
          "once the platform's backend exposes a usage endpoint.",
      );
    });
}
