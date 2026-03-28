# @agentforge/sdk

Minimal TypeScript builder utilities for authoring AgentForge agent definitions.

## Install

```bash
npm install @agentforge/sdk
```

## Usage

```ts
import { Agent, AgentPolicy } from "@agentforge/sdk";

const supportBot = Agent("Support Bot")
  .description("Triages support requests and escalates billing issues.")
  .model("openai", "gpt-4o-mini", 0.2)
  .llmNode("triage", "You are a concise support triage agent.")
  .toolNode("lookupTicket", "tickets.lookup")
  .subagentNode("billingEscalation", "billing-specialist")
  .edge("triage", "lookupTicket")
  .edge("lookupTicket", "billingEscalation", "billing", "contains")
  .policy(
    new AgentPolicy()
      .allowTools("tickets.lookup")
      .requireApprovalFor("billing.refund")
      .denyInputPattern("(?i)api[_-]?key")
      .maxCost(0.25)
      .maxSteps(6)
      .allowFetchOnly("https://docs.agentforge.dev/*")
  );

const definition = supportBot.build();

console.log(definition.graph_definition.entry_point);
console.log(supportBot.toJSON(true));
```

`build()` returns a plain object ready to serialize or send to AgentForge APIs. `toJSON(true)` pretty-prints the same definition with backend-compatible field names.
