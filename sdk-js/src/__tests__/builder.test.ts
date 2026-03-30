import { describe, it, expect } from "vitest";
import { Agent, AgentBuilder, AgentPolicy } from "../builder.js";
import type { AgentDefinition } from "../types.js";

describe("AgentBuilder", () => {
  describe("construction", () => {
    it("creates a builder with default name", () => {
      const builder = Agent();
      expect(builder).toBeInstanceOf(AgentBuilder);
    });

    it("creates a builder with custom name", () => {
      const builder = Agent("MyBot");
      expect(builder).toBeInstanceOf(AgentBuilder);
    });
  });

  describe(".model()", () => {
    it("sets openai model by default in build()", () => {
      const agent = Agent("test").llmNode("n1").build();
      expect(agent.model_config.provider).toBe("openai");
      expect(agent.model_config.model).toBe("gpt-4o");
    });

    it("sets ollama model", () => {
      const agent = Agent("test").model("ollama", "llama3.2").llmNode("n1").build();
      expect(agent.model_config.provider).toBe("ollama");
      expect(agent.model_config.model).toBe("llama3.2");
    });

    it("is chainable", () => {
      const builder = Agent("test").model("ollama", "llama3.2");
      expect(builder).toBeInstanceOf(AgentBuilder);
    });
  });

  describe(".llmNode()", () => {
    it("adds an llm node", () => {
      const agent = Agent("test").llmNode("chat", "Be helpful").build();
      expect(agent.graph_definition.nodes).toHaveLength(1);
      expect(agent.graph_definition.nodes[0].id).toBe("chat");
      expect(agent.graph_definition.nodes[0].type).toBe("llm");
      expect(agent.graph_definition.nodes[0].config.system_prompt).toBe("Be helpful");
    });

    it("first node becomes entry_point", () => {
      const agent = Agent("test").llmNode("first").llmNode("second").build();
      expect(agent.graph_definition.entry_point).toBe("first");
    });
  });

  describe(".toolNode()", () => {
    it("adds a tool node", () => {
      const agent = Agent("test").toolNode("search", "web_search").build();
      const node = agent.graph_definition.nodes[0];
      expect(node.type).toBe("tool");
      expect(node.config.tool_name).toBe("web_search");
    });
  });

  describe(".subagentNode()", () => {
    it("adds a subagent node", () => {
      const agent = Agent("test").subagentNode("delegate", "uuid-123").build();
      const node = agent.graph_definition.nodes[0];
      expect(node.type).toBe("subagent");
      expect(node.config.agent_id).toBe("uuid-123");
    });
  });

  describe(".customNode()", () => {
    it("adds a custom node type", () => {
      const agent = Agent("test").customNode("step1", "my_type", { key: "val" }).build();
      expect(agent.graph_definition.nodes[0].type).toBe("my_type");
    });
  });

  describe(".edge()", () => {
    it("adds a simple edge", () => {
      const agent = Agent("test").llmNode("a").llmNode("b").edge("a", "b").build();
      expect(agent.graph_definition.edges).toHaveLength(1);
      expect(agent.graph_definition.edges[0].from).toBe("a");
      expect(agent.graph_definition.edges[0].to).toBe("b");
    });

    it("adds a conditional edge", () => {
      const agent = Agent("test")
        .llmNode("a")
        .llmNode("b")
        .edge("a", "b", "yes", "contains")
        .build();
      expect(agent.graph_definition.edges[0].condition).toBe("yes");
      expect(agent.graph_definition.edges[0].condition_type).toBe("contains");
    });
  });

  describe(".parallelNodes()", () => {
    it("sets parallel node ids", () => {
      const agent = Agent("test")
        .llmNode("a")
        .llmNode("b")
        .parallelNodes("a", "b")
        .build();
      expect(agent.graph_definition.parallel_nodes).toContain("a");
      expect(agent.graph_definition.parallel_nodes).toContain("b");
    });
  });

  describe(".skill()", () => {
    it("adds an instruction skill", () => {
      const agent = Agent("test")
        .llmNode("n")
        .skill("summarizer", { skillType: "instruction", instructions: "Summarize" })
        .build();
      expect(agent.skills).toHaveLength(1);
      expect(agent.skills[0].name).toBe("summarizer");
      expect(agent.skills[0].skill_type).toBe("instruction");
    });
  });

  describe(".policy()", () => {
    it("attaches policy to agent definition", () => {
      const policy = new AgentPolicy().maxCost(0.5).maxSteps(5);
      const agent = Agent("test").llmNode("n").policy(policy).build();
      expect(agent.execution_policy?.max_cost_usd).toBe(0.5);
      expect(agent.execution_policy?.max_graph_steps).toBe(5);
    });
  });

  describe(".build()", () => {
    it("returns a complete AgentDefinition", () => {
      const agent: AgentDefinition = Agent("MyBot")
        .model("ollama", "llama3.2", 0.5)
        .llmNode("chat", "Be helpful")
        .build();
      expect(agent.name).toBe("MyBot");
      expect(agent.model_config.provider).toBe("ollama");
      expect(agent.graph_definition.nodes).toHaveLength(1);
    });

    it("build does not mutate builder state", () => {
      const builder = Agent("test").llmNode("n");
      const a1 = builder.build();
      const a2 = builder.build();
      expect(a1).not.toBe(a2);
      expect(a1.graph_definition.nodes).toHaveLength(1);
      expect(a2.graph_definition.nodes).toHaveLength(1);
    });
  });

  describe(".toJSON()", () => {
    it("produces valid JSON", () => {
      const json = Agent("test").llmNode("n").toJSON();
      const parsed = JSON.parse(json);
      expect(parsed.name).toBe("test");
    });

    it("produces pretty JSON with pretty=true", () => {
      const json = Agent("test").llmNode("n").toJSON(true);
      expect(json).toContain("\n");
    });
  });
});

describe("AgentPolicy", () => {
  it("builds empty policy", () => {
    const policy = new AgentPolicy().build();
    expect(policy).toEqual({});
  });

  it("sets allowed tools", () => {
    const policy = new AgentPolicy().allowTools("search", "calc").build();
    expect(policy.allowed_tools).toContain("search");
    expect(policy.allowed_tools).toContain("calc");
  });

  it("sets denied tools", () => {
    const policy = new AgentPolicy().denyTool("exec").build();
    expect(policy.denied_tools).toContain("exec");
  });

  it("sets max cost", () => {
    const policy = new AgentPolicy().maxCost(1.0).build();
    expect(policy.max_cost_usd).toBe(1.0);
  });

  it("sets max steps", () => {
    const policy = new AgentPolicy().maxSteps(10).build();
    expect(policy.max_graph_steps).toBe(10);
  });

  it("is chainable", () => {
    const policy = new AgentPolicy();
    expect(policy.maxCost(1).maxSteps(5)).toBe(policy);
  });
});
