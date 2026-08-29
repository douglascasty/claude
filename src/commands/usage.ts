import { Command } from "commander";
import { getProject, listApiKeys } from "../lib/store.js";
import { fail } from "../lib/output.js";

export function registerUsageCommands(program: Command): void {
  program
    .command("usage")
    .description("show API key activity for a project")
    .argument("<projectId>", "project id")
    .action(async (projectId: string) => {
      const project = await getProject(projectId);
      if (!project) {
        fail(`no project found with id "${projectId}"`);
      }
      const keys = await listApiKeys(projectId);
      const active = keys.filter((k) => !k.revokedAt).length;
      const revoked = keys.length - active;

      console.log(`Project: ${project.name} (${project.id})`);
      console.log(`Keys:    ${keys.length} total, ${active} active, ${revoked} revoked`);
      console.log();
      console.log(
        "Note: request-level usage metrics are not tracked yet — this only reflects " +
          "API key counts stored in Supabase.",
      );
    });
}
