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
  /** AgentForge Graph (AFG) schema revision; default 1.0 when omitted on read */
  graph_schema_version?: string;
  nodes: NodeConfig[];
  edges: EdgeConfig[];
  entry_point?: string;
  parallel_nodes?: string[];
}

export interface SkillSpec {
  name: string;
  description?: string;
  skill_type?: SkillType;
  source_code?: string;
  instructions?: string;
  metadata?: Record<string, JsonValue>;
}

/** Matches backend ExecutionPolicyValidated field names. */
export interface PolicyConfig {
  allowed_tools?: string[];
  denied_tools?: string[];
  allowed_fetch_url_prefixes?: string[];
  max_graph_steps?: number;
  deny_patterns?: string[];
  require_human_approval_for?: string[];
  max_cost_usd?: number;
  max_message_history?: number;
  context_compression_threshold?: number;
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
