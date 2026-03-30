import { describe, it, expect } from "vitest";
import type {
  NodeConfig,
  EdgeConfig,
  GraphDefinition,
  AgentModelConfig,
  PolicyConfig,
  SkillSpec,
  AgentDefinition,
} from "../types.js";

describe("TypeScript types shape", () => {
  it("NodeConfig has required fields", () => {
    const node: NodeConfig = { id: "n1", type: "llm", config: {} };
    expect(node.id).toBe("n1");
    expect(node.type).toBe("llm");
  });

  it("NodeConfig accepts custom type", () => {
    const node: NodeConfig = { id: "n1", type: "my_custom", config: { key: 42 } };
    expect(node.type).toBe("my_custom");
  });

  it("EdgeConfig uses from/to", () => {
    const edge: EdgeConfig = { from: "a", to: "b", condition_type: "always" };
    expect(edge.from).toBe("a");
    expect(edge.to).toBe("b");
  });

  it("EdgeConfig condition is optional", () => {
    const edge: EdgeConfig = { from: "a", to: "b" };
    expect(edge.condition).toBeUndefined();
  });

  it("AgentModelConfig has required fields", () => {
    const mc: AgentModelConfig = { provider: "ollama", model: "llama3.2", temperature: 0.7 };
    expect(mc.provider).toBe("ollama");
  });

  it("PolicyConfig all fields optional", () => {
    const p: PolicyConfig = {};
    expect(p.max_cost_usd).toBeUndefined();
    expect(p.max_graph_steps).toBeUndefined();
  });

  it("PolicyConfig can set values", () => {
    const p: PolicyConfig = {
      max_cost_usd: 0.5,
      max_graph_steps: 10,
      denied_tools: ["exec"],
      allowed_tools: ["search"],
    };
    expect(p.max_cost_usd).toBe(0.5);
    expect(p.denied_tools).toContain("exec");
  });

  it("SkillSpec instruction type", () => {
    const s: SkillSpec = { name: "sum", skill_type: "instruction", instructions: "Summarize" };
    expect(s.skill_type).toBe("instruction");
  });

  it("SkillSpec code type", () => {
    const s: SkillSpec = { name: "calc", skill_type: "code", source_code: "def run(x): return x" };
    expect(s.skill_type).toBe("code");
  });

  it("AgentDefinition complete shape", () => {
    const agent: AgentDefinition = {
      name: "TestBot",
      graph_definition: {
        nodes: [{ id: "n1", type: "llm", config: {} }],
        edges: [],
        entry_point: "n1",
      },
      model_config: { provider: "ollama", model: "llama3.2", temperature: 0.7 },
      skills: [],
    };
    expect(agent.name).toBe("TestBot");
    expect(agent.description).toBeUndefined();
    expect(agent.execution_policy).toBeUndefined();
  });

  it("GraphDefinition with parallel_nodes", () => {
    const gd: GraphDefinition = {
      nodes: [
        { id: "a", type: "llm", config: {} },
        { id: "b", type: "llm", config: {} },
      ],
      edges: [],
      entry_point: "a",
      parallel_nodes: ["a", "b"],
    };
    expect(gd.parallel_nodes).toContain("a");
  });
});
