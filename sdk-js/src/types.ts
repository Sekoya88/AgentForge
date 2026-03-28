export type NodeType = "llm" | "tool" | "subagent" | "conditional" | "interrupt";

export type ConditionType = "contains" | "regex" | "json_path" | "always";

export type SkillType = "code" | "instruction";

export type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };

export interface NodeConfig {
  id: string;
  type: string;
  config: Record<string, unknown>;
}

export interface EdgeConfig {
  from: string;
  to: string;
  condition?: string;
  condition_type?: ConditionType;
}

export interface GraphDefinition {
  nodes: NodeConfig[];
  edges: EdgeConfig[];
  entry_point?: string;
}

export interface SkillSpec {
  name: string;
  description?: string;
  skill_type?: SkillType;
  source_code?: string;
  instructions?: string;
  metadata?: Record<string, JsonValue>;
}

export interface PolicyConfig {
  allow_tools?: string[];
  deny_tools?: string[];
  require_approval_for?: string[];
  deny_input_pattern?: string;
  max_cost_usd?: number;
  max_steps?: number;
  allowed_urls?: string[];
}

export interface AgentModelConfig {
  provider: string;
  model: string;
  temperature: number;
}

export interface AgentDefinition {
  name: string;
  description?: string;
  graph_definition: GraphDefinition;
  model_config: AgentModelConfig;
  skills: SkillSpec[];
  execution_policy?: PolicyConfig;
}

export interface SkillOptions {
  description?: string;
  skillType?: SkillType;
  sourceCode?: string;
  instructions?: string;
  metadata?: Record<string, JsonValue>;
}
