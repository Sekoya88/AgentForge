#!/usr/bin/env node
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";
import { AgentClient } from "./client.js";

async function main() {
  const args = process.argv.slice(2);
  if (args.length < 2) {
    console.error("Usage: agentforge push <agent-file.js>");
    process.exit(1);
  }

  const command = args[0];
  const file = args[1];

  if (command !== "push") {
    console.error(`Unknown command: ${command}`);
    process.exit(1);
  }

  const absolutePath = resolve(process.cwd(), file);
  const fileUrl = pathToFileURL(absolutePath).href;

  try {
    // Dynamically import the user's agent module
    const mod = await import(fileUrl);

    let definitionStr: string | undefined;

    // Auto-detect the exported agent
    for (const key of Object.keys(mod)) {
      const exported = mod[key];
      // 1. Is it an AgentBuilder? (has .toJSON)
      if (typeof exported === "object" && exported !== null && typeof exported.toJSON === "function") {
         definitionStr = exported.toJSON();
         break;
      }
      // 2. Is it a raw AgentDefinition?
      if (typeof exported === "object" && exported !== null && exported.graph_definition && exported.name) {
         definitionStr = JSON.stringify(exported);
         break;
      }
    }

    if (!definitionStr) {
      console.error("Could not find an exported AgentBuilder or AgentDefinition in the specified file.");
      process.exit(1);
    }

    const client = new AgentClient();
    const parsed = JSON.parse(definitionStr);
    console.log(`Pushing agent '${parsed.name}' to AgentForge...`);

    const result = await client.push(definitionStr);
    console.log(`Successfully pushed agent! ID: ${result.id}`);

  } catch (e) {
    console.error("Error executing push:", e instanceof Error ? e.message : e);
    process.exit(1);
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
