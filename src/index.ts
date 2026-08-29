#!/usr/bin/env node
import { Command } from "commander";
import { registerAuthCommands } from "./commands/auth.js";
import { registerConfigCommands } from "./commands/config.js";
import { registerProjectCommands } from "./commands/projects.js";
import { registerKeyCommands } from "./commands/keys.js";
import { registerUsageCommands } from "./commands/usage.js";
import { registerHealthCommands } from "./commands/health.js";

const program = new Command();

program
  .name("claude-console")
  .description("CLI for the Claude Code Console developer platform")
  .version("0.1.0");

registerAuthCommands(program);
registerConfigCommands(program);
registerProjectCommands(program);
registerKeyCommands(program);
registerUsageCommands(program);
registerHealthCommands(program);

program.parseAsync(process.argv).catch((err) => {
  console.error(err instanceof Error ? err.message : err);
  process.exit(1);
});
