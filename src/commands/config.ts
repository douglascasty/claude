import { Command } from "commander";
import { loadState, saveState } from "../lib/store.js";
import { printTable, fail } from "../lib/output.js";

export function registerConfigCommands(program: Command): void {
  const config = program.command("config").description("manage local CLI configuration");

  config
    .command("set")
    .description("set a config value")
    .argument("<key>", "config key")
    .argument("<value>", "config value")
    .action((key: string, value: string) => {
      const state = loadState();
      state.config[key] = value;
      saveState(state);
      console.log(`${key} = ${value}`);
    });

  config
    .command("get")
    .description("get a config value")
    .argument("<key>", "config key")
    .action((key: string) => {
      const state = loadState();
      const value = state.config[key];
      if (value === undefined) {
        fail(`no config value set for "${key}"`);
      }
      console.log(value);
    });

  config
    .command("list")
    .description("list all config values")
    .action(() => {
      const state = loadState();
      const rows = Object.entries(state.config).map(([key, value]) => ({ key, value }));
      printTable(rows);
    });

  config
    .command("unset")
    .description("remove a config value")
    .argument("<key>", "config key")
    .action((key: string) => {
      const state = loadState();
      delete state.config[key];
      saveState(state);
      console.log(`Unset ${key}.`);
    });
}
