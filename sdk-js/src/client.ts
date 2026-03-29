import type { AgentDefinition } from "./types.js";

export interface AgentClientConfig {
  apiUrl?: string;
  token?: string;
}

export class AgentClient {
  private apiUrl: string;
  private token: string;

  constructor(config?: AgentClientConfig) {
    this.apiUrl = config?.apiUrl ?? process.env.AGENTFORGE_API_URL ?? "http://localhost:8000";
    this.token = config?.token ?? process.env.AGENTFORGE_TOKEN ?? "";
  }

  private get headers(): Record<string, string> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      Accept: "application/json",
    };
    if (this.token) {
      headers["Authorization"] = `Bearer ${this.token}`;
    }
    return headers;
  }

  /**
   * Pushes an AgentDefinition to the platform.
   * If the agent already exists (matched by name during import in the backend),
   * it creates a new version.
   */
  async push(definition: AgentDefinition | string): Promise<{ id: string }> {
    const payload = typeof definition === "string" ? definition : JSON.stringify(definition);

    // The import endpoint handles full agent definitions
    const res = await fetch(`${this.apiUrl}/api/v1/agents/import`, {
      method: "POST",
      headers: this.headers,
      body: payload,
    });

    if (!res.ok) {
      let errorBody = "";
      try {
        errorBody = await res.text();
      } catch (e) {
        // ignore
      }
      throw new Error(`Failed to push agent: ${res.status} ${res.statusText} - ${errorBody}`);
    }

    // Usually returns { id: "..." } or the created agent object containing "id"
    const data = (await res.json()) as { id: string } | any;
    return { id: data.id || data.agent_id || "unknown" };
  }

  /**
   * Pulls an AgentDefinition from the platform.
   */
  async pull(id: string, includeSkills = true): Promise<AgentDefinition> {
    const res = await fetch(`${this.apiUrl}/api/v1/agents/${id}/export?include_skills=${includeSkills}`, {
      method: "GET",
      headers: this.headers,
    });

    if (!res.ok) {
      let errorBody = "";
      try {
        errorBody = await res.text();
      } catch (e) {
        // ignore
      }
      throw new Error(`Failed to pull agent: ${res.status} ${res.statusText} - ${errorBody}`);
    }

    return (await res.json()) as AgentDefinition;
  }
}
