import { Command } from "commander";
import { fail } from "../lib/output.js";

export function registerUsageCommands(program: Command): void {
  program
    .command("usage")
    .description("reserved for future usage reporting")
    .action(() => {
      fail("Usage reporting is not implemented yet.");
    });
}
