import type {
  AgentDefinition,
  AgentModelConfig,
  ConditionType,
  EdgeConfig,
  GraphDefinition,
  NodeConfig,
  PolicyConfig,
  SkillOptions,
  SkillSpec,
} from "./types.js";

function cloneNode(node: NodeConfig): NodeConfig {
  return {
    ...node,
    config: { ...node.config },
  };
}

function cloneEdge(edge: EdgeConfig): EdgeConfig {
  return { ...edge };
}

function cloneSkill(skill: SkillSpec): SkillSpec {
  return {
    ...skill,
    ...(skill.metadata ? { metadata: { ...skill.metadata } } : {}),
  };
}

function clonePolicy(policy?: PolicyConfig): PolicyConfig | undefined {
  if (!policy) {
    return undefined;
  }

  return {
    ...(policy.allow_tools ? { allow_tools: [...policy.allow_tools] } : {}),
    ...(policy.deny_tools ? { deny_tools: [...policy.deny_tools] } : {}),
    ...(policy.require_approval_for
      ? { require_approval_for: [...policy.require_approval_for] }
      : {}),
    ...(policy.deny_input_pattern
      ? { deny_input_pattern: policy.deny_input_pattern }
      : {}),
    ...(policy.max_cost_usd !== undefined ? { max_cost_usd: policy.max_cost_usd } : {}),
    ...(policy.max_steps !== undefined ? { max_steps: policy.max_steps } : {}),
    ...(policy.allowed_urls ? { allowed_urls: [...policy.allowed_urls] } : {}),
  };
}

function appendItems(values: string[] | undefined, items: string[]): string[] {
  return [...(values ?? []), ...items];
}

export class AgentPolicy {
  private policyConfig: PolicyConfig;

  constructor(initial?: PolicyConfig) {
    this.policyConfig = clonePolicy(initial) ?? {};
  }

  allowTools(...tools: string[]): this {
    this.policyConfig.allow_tools = appendItems(this.policyConfig.allow_tools, tools);
    return this;
  }

  denyTool(...tools: string[]): this {
    this.policyConfig.deny_tools = appendItems(this.policyConfig.deny_tools, tools);
    return this;
  }

  requireApprovalFor(...tools: string[]): this {
    this.policyConfig.require_approval_for = appendItems(
      this.policyConfig.require_approval_for,
      tools,
    );
    return this;
  }

  denyInputPattern(pattern: string): this {
    this.policyConfig.deny_input_pattern = pattern;
    return this;
  }

  maxCost(cost: number, currency = "USD"): this {
    void currency;
    this.policyConfig.max_cost_usd = cost;
    return this;
  }

  maxSteps(steps: number): this {
    this.policyConfig.max_steps = steps;
    return this;
  }

  allowFetchOnly(...urls: string[]): this {
    this.policyConfig.allowed_urls = appendItems(this.policyConfig.allowed_urls, urls);
    return this;
  }

  build(): PolicyConfig {
    return clonePolicy(this.policyConfig) ?? {};
  }
}

export class AgentBuilder {
  private readonly agentName: string;
  private agentDescription: string | undefined;
  private nodes: NodeConfig[] = [];
  private edges: EdgeConfig[] = [];
  private entryPoint: string | undefined;
  private skills: SkillSpec[] = [];
  private executionPolicy: PolicyConfig | undefined;
  private modelConfig: AgentModelConfig = {
    provider: "openai",
    model: "gpt-4o",
    temperature: 0.7,
  };

  constructor(name = "My Agent") {
    this.agentName = name;
  }

  description(description: string): this {
    this.agentDescription = description;
    return this;
  }

  model(provider: string, model: string, temperature = 0.7): this {
    this.modelConfig = {
      provider,
      model,
      temperature,
    };
    return this;
  }

  llmNode(id: string, systemPrompt = ""): this {
    return this.addNode({
      id,
      type: "llm",
      config: { system_prompt: systemPrompt },
    });
  }

  toolNode(id: string, toolName: string): this {
    return this.addNode({
      id,
      type: "tool",
      config: { tool_name: toolName },
    });
  }

  subagentNode(id: string, agentId: string): this {
    return this.addNode({
      id,
      type: "subagent",
      config: { agent_id: agentId },
    });
  }

  customNode(id: string, nodeType: string, config: Record<string, unknown>): this {
    return this.addNode({
      id,
      type: nodeType,
      config,
    });
  }

  edge(from: string, to: string, condition?: string, conditionType: ConditionType = "always"): this {
    this.edges.push({
      from,
      to,
      ...(condition !== undefined ? { condition } : {}),
      condition_type: conditionType,
    });
    return this;
  }

  policy(policy: AgentPolicy | PolicyConfig): this {
    this.executionPolicy = policy instanceof AgentPolicy ? policy.build() : clonePolicy(policy);
    return this;
  }

  skill(name: string, options: SkillOptions = {}): this {
    const skill: SkillSpec = {
      name,
      skill_type: options.skillType ?? "instruction",
      ...(options.description ? { description: options.description } : {}),
      ...(options.sourceCode ? { source_code: options.sourceCode } : {}),
      ...(options.instructions ? { instructions: options.instructions } : {}),
      ...(options.metadata ? { metadata: options.metadata } : {}),
    };

    this.skills.push(skill);
    return this;
  }

  build(): AgentDefinition {
    const graphDefinition: GraphDefinition = {
      nodes: this.nodes.map(cloneNode),
      edges: this.edges.map(cloneEdge),
      ...(this.entryPoint ? { entry_point: this.entryPoint } : {}),
    };

    const definition: AgentDefinition = {
      name: this.agentName,
      graph_definition: graphDefinition,
      model_config: { ...this.modelConfig },
      skills: this.skills.map(cloneSkill),
    };

    if (this.agentDescription) {
      definition.description = this.agentDescription;
    }

    if (this.executionPolicy) {
      definition.execution_policy = clonePolicy(this.executionPolicy) ?? {};
    }

    return definition;
  }

  toJSON(pretty = false): string {
    return JSON.stringify(this.build(), null, pretty ? 2 : undefined);
  }

  private addNode(node: NodeConfig): this {
    if (!this.entryPoint) {
      this.entryPoint = node.id;
    }

    this.nodes.push(cloneNode(node));
    return this;
  }
}

export function Agent(name = "My Agent"): AgentBuilder {
  return new AgentBuilder(name);
}
