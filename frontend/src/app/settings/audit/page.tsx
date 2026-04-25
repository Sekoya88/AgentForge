"use client";

import { useEffect, useState } from "react";
import { ToolShell } from "@/components/layout/ToolShell";

interface AuditEntry {
  id: string;
  event_type: string;
  resource_type: string;
  resource_id: string | null;
  payload: Record<string, unknown>;
  created_at: string;
}

const EVENT_TYPE_OPTIONS = [
  { value: "", label: "All events" },
  { value: "agent.created", label: "Agent created" },
  { value: "agent.updated", label: "Agent updated" },
  { value: "agent.deleted", label: "Agent deleted" },
];

function eventBadge(eventType: string) {
  if (eventType.endsWith(".created")) {
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
        {eventType}
      </span>
    );
  }
  if (eventType.endsWith(".deleted")) {
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-red-500/20 text-red-300 border border-red-500/40">
        {eventType}
      </span>
    );
  }
  if (eventType.endsWith(".updated")) {
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40">
        {eventType}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-blue-500/20 text-blue-300 border border-blue-500/40">
      {eventType}
    </span>
  );
}

function PayloadCell({ payload }: { payload: Record<string, unknown> }) {
  const [expanded, setExpanded] = useState(false);
  const isEmpty = Object.keys(payload).length === 0;

  if (isEmpty) {
    return <span className="text-zinc-600 text-xs">—</span>;
  }

  return (
    <div>
      {expanded ? (
        <div>
          <pre className="text-xs text-zinc-300 bg-zinc-900 rounded p-2 max-w-xs overflow-x-auto whitespace-pre-wrap break-all">
            {JSON.stringify(payload, null, 2)}
          </pre>
          <button
            onClick={() => setExpanded(false)}
            className="mt-1 text-xs text-zinc-400 hover:text-zinc-200 underline"
          >
            Collapse
          </button>
        </div>
      ) : (
        <button
          onClick={() => setExpanded(true)}
          className="text-xs text-blue-400 hover:text-blue-300 underline"
        >
          View
        </button>
      )}
    </div>
  );
}

export default function AuditLogPage() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [eventTypeFilter, setEventTypeFilter] = useState("");
  const [resourceTypeFilter, setResourceTypeFilter] = useState("");

  useEffect(() => {
    const params = new URLSearchParams({ limit: "50" });
    if (eventTypeFilter) params.set("event_type", eventTypeFilter);
    if (resourceTypeFilter) params.set("resource_type", resourceTypeFilter);

    setLoading(true);
    setError(null);

    fetch(`/api/v1/settings/audit?${params.toString()}`, {
      credentials: "include",
    })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data) => {
        setEntries(data.items ?? []);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [eventTypeFilter, resourceTypeFilter]);

  return (
    <ToolShell active="settings">
      <div className="max-w-6xl mx-auto px-6 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white tracking-tight">Audit Log</h1>
          <p className="text-zinc-400 mt-1 text-sm">
            Track all actions performed on your agents and resources.
          </p>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap gap-3 mb-6">
          <select
            value={eventTypeFilter}
            onChange={(e) => setEventTypeFilter(e.target.value)}
            className="bg-zinc-900 border border-zinc-700 text-zinc-200 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
          >
            {EVENT_TYPE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>

          <input
            type="text"
            placeholder="Filter by resource type..."
            value={resourceTypeFilter}
            onChange={(e) => setResourceTypeFilter(e.target.value)}
            className="bg-zinc-900 border border-zinc-700 text-zinc-200 text-sm rounded-lg px-3 py-2 placeholder-zinc-600 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
          />
        </div>

        {/* Content */}
        {loading && (
          <div className="flex items-center justify-center py-16">
            <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        {error && (
          <div className="bg-red-900/30 border border-red-700/50 rounded-xl p-4 text-red-300 text-sm">
            Failed to load audit log: {error}
          </div>
        )}

        {!loading && !error && entries.length === 0 && (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <span className="material-symbols-outlined text-5xl text-zinc-600 mb-4">
              manage_search
            </span>
            <p className="text-zinc-400 text-lg font-medium">No audit events found</p>
            <p className="text-zinc-600 text-sm mt-1">
              Events will appear here as you interact with your agents.
            </p>
          </div>
        )}

        {!loading && !error && entries.length > 0 && (
          <div className="bg-zinc-900/60 border border-zinc-800 rounded-2xl overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800 bg-zinc-900/80">
                  <th className="text-left px-5 py-3.5 text-zinc-400 font-semibold text-xs uppercase tracking-wider">
                    Event
                  </th>
                  <th className="text-left px-5 py-3.5 text-zinc-400 font-semibold text-xs uppercase tracking-wider">
                    Resource
                  </th>
                  <th className="text-left px-5 py-3.5 text-zinc-400 font-semibold text-xs uppercase tracking-wider">
                    Resource ID
                  </th>
                  <th className="text-left px-5 py-3.5 text-zinc-400 font-semibold text-xs uppercase tracking-wider">
                    Payload
                  </th>
                  <th className="text-left px-5 py-3.5 text-zinc-400 font-semibold text-xs uppercase tracking-wider">
                    Timestamp
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/60">
                {entries.map((entry) => (
                  <tr
                    key={entry.id}
                    className="hover:bg-zinc-800/30 transition-colors"
                  >
                    <td className="px-5 py-3.5">{eventBadge(entry.event_type)}</td>
                    <td className="px-5 py-3.5 text-zinc-300 font-mono text-xs">
                      {entry.resource_type}
                    </td>
                    <td className="px-5 py-3.5 text-zinc-400 font-mono text-xs truncate max-w-[140px]">
                      {entry.resource_id ?? <span className="text-zinc-600">—</span>}
                    </td>
                    <td className="px-5 py-3.5">
                      <PayloadCell payload={entry.payload} />
                    </td>
                    <td className="px-5 py-3.5 text-zinc-500 text-xs whitespace-nowrap">
                      {new Date(entry.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </ToolShell>
  );
}
