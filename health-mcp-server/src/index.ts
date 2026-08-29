#!/usr/bin/env node
/**
 * MCP server for personal health data: connect a provider (Apple Health,
 * Google Health Connect), import records exported from that provider's app,
 * and list/summarize them. Runs locally over stdio and shares its state
 * file with the sibling `claude-console` CLI's `health` command.
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { registerHealthTools } from "./tools/health.js";

const server = new McpServer({
  name: "health-mcp-server",
  version: "1.0.0",
});

registerHealthTools(server);

async function main(): Promise<void> {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("health-mcp-server running on stdio");
}

main().catch((error) => {
  console.error("Server error:", error);
  process.exit(1);
});
