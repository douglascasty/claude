import { Command } from "commander";
import { randomUUID } from "node:crypto";
import { loadState, saveState } from "../lib/store.js";
import { fail } from "../lib/output.js";

export function registerAuthCommands(program: Command): void {
  const auth = program.command("auth").description("manage your Console session");

  auth
    .command("login")
    .description("log in to the Claude Code Console")
    .argument("<email>", "account email")
    .action((email: string) => {
      const state = loadState();
      state.session = {
        email,
        token: randomUUID(),
        loggedInAt: new Date().toISOString(),
      };
      saveState(state);
      console.log(`Logged in as ${email}.`);
    });

  auth
    .command("logout")
    .description("clear the local session")
    .action(() => {
      const state = loadState();
      if (!state.session) {
        console.log("Already logged out.");
        return;
      }
      state.session = null;
      saveState(state);
      console.log("Logged out.");
    });

  auth
    .command("whoami")
    .description("show the currently logged-in account")
    .action(() => {
      const state = loadState();
      if (!state.session) {
        fail("not logged in. Run `claude-console auth login <email>`.");
      }
      console.log(state.session.email);
    });
}
