import { Command } from "commander";
import { listProjects, createProject, getProject, deleteProject } from "../lib/store.js";
import { printTable, fail } from "../lib/output.js";

export function registerProjectCommands(program: Command): void {
  const projects = program.command("projects").description("manage Console projects");

  projects
    .command("create")
    .description("create a new project")
    .argument("<name>", "project name")
    .action(async (name: string) => {
      const project = await createProject(name);
      console.log(`Created project ${project.name} (${project.id}).`);
    });

  projects
    .command("list")
    .description("list all projects")
    .action(async () => {
      const all = await listProjects();
      printTable(
        all.map((p) => ({
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
    .action(async (id: string) => {
      const project = await getProject(id);
      if (!project) {
        fail(`no project found with id "${id}"`);
      }
      console.log(`id:      ${project.id}`);
      console.log(`name:    ${project.name}`);
      console.log(`created: ${project.createdAt}`);
    });

  projects
    .command("delete")
    .description("delete a project")
    .argument("<id>", "project id")
    .action(async (id: string) => {
      const deleted = await deleteProject(id);
      if (!deleted) {
        fail(`no project found with id "${id}"`);
      }
      console.log(`Deleted project ${id}.`);
    });
}
