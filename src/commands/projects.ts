import { Command } from "commander";
import { loadState, saveState, newId } from "../lib/store.js";
import { printTable, fail } from "../lib/output.js";

export function registerProjectCommands(program: Command): void {
  const projects = program.command("projects").description("manage Console projects");

  projects
    .command("create")
    .description("create a new project")
    .argument("<name>", "project name")
    .action((name: string) => {
      const state = loadState();
      const project = { id: newId("proj"), name, createdAt: new Date().toISOString() };
      state.projects.push(project);
      saveState(state);
      console.log(`Created project ${project.name} (${project.id}).`);
    });

  projects
    .command("list")
    .description("list all projects")
    .action(() => {
      const state = loadState();
      printTable(
        state.projects.map((p) => ({
          id: p.id,
          name: p.name,
          created: p.createdAt,
        })),
      );
    });

  projects
    .command("show")
    .description("show a single project")
    .argument("<id>", "project id")
    .action((id: string) => {
      const state = loadState();
      const project = state.projects.find((p) => p.id === id);
      if (!project) {
        fail(`no project found with id "${id}"`);
      }
      const keyCount = state.apiKeys.filter((k) => k.projectId === id && !k.revokedAt).length;
      console.log(`id:      ${project.id}`);
      console.log(`name:    ${project.name}`);
      console.log(`created: ${project.createdAt}`);
      console.log(`keys:    ${keyCount} active`);
    });

  projects
    .command("delete")
    .description("delete a project and its API keys")
    .argument("<id>", "project id")
    .action((id: string) => {
      const state = loadState();
      const before = state.projects.length;
      state.projects = state.projects.filter((p) => p.id !== id);
      if (state.projects.length === before) {
        fail(`no project found with id "${id}"`);
      }
      state.apiKeys = state.apiKeys.filter((k) => k.projectId !== id);
      saveState(state);
      console.log(`Deleted project ${id}.`);
    });
}
