import { describe, it, expect, vi, beforeEach } from "vitest";
import { AgentClient } from "../client.js";

describe("AgentClient", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  describe("constructor", () => {
    it("accepts custom config", () => {
      const client = new AgentClient({ apiUrl: "http://custom:9000", token: "mytoken" });
      expect(client).toBeInstanceOf(AgentClient);
    });
  });

  describe(".push()", () => {
    it("calls POST /api/v1/agents/import with agent JSON", async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ id: "agent-uuid-123" }),
      });
      vi.stubGlobal("fetch", mockFetch);

      const client = new AgentClient({ apiUrl: "http://localhost:8000", token: "tok" });
      const agentDef = {
        name: "TestBot",
        graph_definition: { nodes: [{ id: "n1", type: "llm", config: {} }], edges: [] },
        model_config: { provider: "ollama", model: "llama3.2", temperature: 0.7 },
        skills: [],
      };

      const result = await client.push(agentDef);

      expect(mockFetch).toHaveBeenCalledOnce();
      const [url, options] = mockFetch.mock.calls[0];
      expect(url).toBe("http://localhost:8000/api/v1/agents/import");
      expect(options.method).toBe("POST");
      expect(options.headers["Content-Type"]).toBe("application/json");
      expect(options.headers["Authorization"]).toBe("Bearer tok");
      expect(result.id).toBe("agent-uuid-123");
    });

    it("throws on non-ok response", async () => {
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        statusText: "Unauthorized",
        text: async () => "Unauthorized",
      }));

      const client = new AgentClient();
      await expect(
        client.push({ name: "t", graph_definition: { nodes: [{ id: "n", type: "llm", config: {} }], edges: [] }, model_config: { provider: "openai", model: "gpt-4o", temperature: 0.7 }, skills: [] })
      ).rejects.toThrow("Failed to push agent: 401");
    });

    it("accepts a JSON string payload", async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ id: "str-id" }),
      });
      vi.stubGlobal("fetch", mockFetch);

      const client = new AgentClient();
      const result = await client.push('{"name":"raw"}');
      expect(result.id).toBe("str-id");

      const [, options] = mockFetch.mock.calls[0];
      expect(options.body).toBe('{"name":"raw"}');
    });
  });

  describe(".pull()", () => {
    it("calls GET /api/v1/agents/{id}/export", async () => {
      const mockDef = {
        name: "PulledBot",
        graph_definition: { nodes: [], edges: [] },
        model_config: { provider: "openai", model: "gpt-4o", temperature: 0.7 },
        skills: [],
      };
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
        ok: true,
        json: async () => mockDef,
      }));

      const client = new AgentClient({ apiUrl: "http://localhost:8000" });
      const result = await client.pull("agent-uuid");
      expect(result.name).toBe("PulledBot");

      const [url] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
      expect(url).toContain("/api/v1/agents/agent-uuid/export");
    });

    it("throws on non-ok response", async () => {
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        statusText: "Not Found",
        text: async () => "Not found",
      }));

      const client = new AgentClient();
      await expect(client.pull("bad-id")).rejects.toThrow("Failed to pull agent: 404");
    });
  });
});
