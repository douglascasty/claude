import { Command } from "commander";
import { fail } from "../lib/output.js";

export function registerKeyCommands(program: Command): void {
  program
    .command("keys")
    .description("reserved for future secure credential management")
    .action(() => {
      fail("API key management is disabled until a secure storage design is implemented.");
    });
}
