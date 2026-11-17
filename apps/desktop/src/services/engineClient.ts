import type {
  AgentNodeConfig,
  AgentTeam,
  EngineHealth,
  ExecutionStep,
  FileArtifact,
  HITLApprovalItem,
  MCPServerItem,
  WorkspaceFolder,
} from "@/types/aksa";

const DEFAULT_BASE_URL = "http://127.0.0.1:43120";

export async function fetchEngineHealth(): Promise<EngineHealth> {
  try {
    const res = await fetch(`${DEFAULT_BASE_URL}/api/v1/health`);
    if (!res.ok) throw new Error("Health check failed");
    const data = await res.json();
    const isOllamaOnline = Boolean(data.ollama?.online);
    return {
      online: true,
      version: data.version ?? "0.1.0",
      ollama_online: isOllamaOnline,
      ollama_models:
        isOllamaOnline && Array.isArray(data.ollama?.models) ? data.ollama.models : [],
      telegram_connected: Boolean(data.telegram?.connected),
      telegram_bot_username: data.telegram?.bot_username ?? null,
    };
  } catch {
    return {
      online: false,
      version: "0.1.0",
      ollama_online: false,
      ollama_models: [],
      telegram_connected: false,
      telegram_bot_username: null,
    };
  }
}

export async function fetchTokenAnalytics(): Promise<{
  total_tokens_used: number;
  total_tokens_saved: number;
  savings_percentage: number;
  total_cost_usd: number;
  total_calls: number;
} | null> {
  try {
    const res = await fetch(`${DEFAULT_BASE_URL}/api/v1/tokens/analytics`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function fetchConfiguredProviders(): Promise<Record<string, boolean> | null> {
  try {
    const res = await fetch(`${DEFAULT_BASE_URL}/api/v1/models/providers`);
    if (!res.ok) return null;
    const data = await res.json();
    const map: Record<string, boolean> = {};
    if (Array.isArray(data.providers)) {
      for (const p of data.providers) {
        map[p.id] = Boolean(p.configured);
      }
    }
    return map;
  } catch {
    return null;
  }
}

export async function fetchProviderDetails(): Promise<{
  configured: Record<string, boolean>;
  apiKeys: Record<string, string>;
  providers: any[];
} | null> {
  try {
    const res = await fetch(`${DEFAULT_BASE_URL}/api/v1/models/providers`);
    if (!res.ok) return null;
    const data = await res.json();
    const configured: Record<string, boolean> = {};
    const apiKeys: Record<string, string> = {};
    if (Array.isArray(data.providers)) {
      for (const p of data.providers) {
        configured[p.id] = Boolean(p.configured);
        if (p.api_key_masked || p.api_key) {
          apiKeys[p.id] = p.api_key_masked || p.api_key;
        }
      }
    }
    return { configured, apiKeys, providers: data.providers };
  } catch {
    return null;
  }
}

export async function fetchAgentTeams(): Promise<AgentTeam[] | null> {
  try {
    const res = await fetch(`${DEFAULT_BASE_URL}/api/v1/teams`);
    if (!res.ok) return null;
    const data = await res.json();
    return data.teams ?? null;
  } catch {
    return null;
  }
}

export async function fetchWorkspaces(): Promise<WorkspaceFolder[] | null> {
  try {
    const res = await fetch(`${DEFAULT_BASE_URL}/api/v1/workspaces`);
    if (!res.ok) return null;
    const data = await res.json();
    return data.workspaces ?? null;
  } catch {
    return null;
  }
}

export async function saveAgentUpdate(
  agentId: string,
  updates: Partial<AgentNodeConfig>
): Promise<AgentNodeConfig | null> {
  try {
    const res = await fetch(`${DEFAULT_BASE_URL}/api/v1/agents/${agentId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updates),
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data.agent ?? null;
  } catch {
    return null;
  }
}

export async function deleteAgentRemote(agentId: string): Promise<boolean> {
  try {
    const res = await fetch(`${DEFAULT_BASE_URL}/api/v1/agents/${agentId}`, {
      method: "DELETE",
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function saveProviderApiKey(provider: string, apiKey: string): Promise<boolean> {
  try {
    const res = await fetch(`${DEFAULT_BASE_URL}/api/v1/models/keys`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider, api_key: apiKey }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function testModelConnectionRemote(params: {
  provider: string;
  model_id: string;
}): Promise<{ ok: boolean; reply?: string; simulated?: boolean; error?: string }> {
  try {
    const res = await fetch(`${DEFAULT_BASE_URL}/api/v1/models/test`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      return { ok: false, error: err.detail || "Gagal menghubungi model" };
    }
    const data = await res.json();
    return { ok: true, reply: data.reply, simulated: data.simulated };
  } catch (err: any) {
    return { ok: false, error: err?.message || "Tidak dapat terhubung ke engine" };
  }
}

export async function createWorkspaceRemote(workspace: {
  name: string;
  folder_path: string;
  allow_read?: boolean;
  allow_write?: boolean;
  allow_execute?: boolean;
}): Promise<WorkspaceFolder | null> {
  try {
    const res = await fetch(`${DEFAULT_BASE_URL}/api/v1/workspaces`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(workspace),
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data.workspace ?? null;
  } catch {
    return null;
  }
}

export async function deleteWorkspaceRemote(workspaceId: string): Promise<boolean> {
  try {
    const res = await fetch(`${DEFAULT_BASE_URL}/api/v1/workspaces/${workspaceId}`, {
      method: "DELETE",
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function openFileInDefaultApp(filePath: string): Promise<boolean> {
  try {
    const res = await fetch(`${DEFAULT_BASE_URL}/api/v1/system/open-path`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: filePath }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function executeTaskOnEngine(params: {
  prompt: string;
  team_id?: string;
  workspace_id?: string;
  workspace_path?: string;
}): Promise<{
  supervisor_name: string;
  reply: string;
  execution_steps: ExecutionStep[];
  artifacts: FileArtifact[];
  tokens_used: number;
  tokens_saved: number;
} | null> {
  try {
    const res = await fetch(`${DEFAULT_BASE_URL}/api/v1/orchestrate/execute`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function fetchHITLApprovals(): Promise<HITLApprovalItem[] | null> {
  try {
    const res = await fetch(`${DEFAULT_BASE_URL}/api/v1/sandbox/approvals`);
    if (!res.ok) return null;
    const data = await res.json();
    return data.approvals ?? null;
  } catch {
    return null;
  }
}

export async function resolveHITLApprovalRemote(
  requestId: string,
  approved: boolean
): Promise<HITLApprovalItem | null> {
  try {
    const res = await fetch(
      `${DEFAULT_BASE_URL}/api/v1/sandbox/approvals/${requestId}/resolve`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approved }),
      }
    );
    if (!res.ok) return null;
    const data = await res.json();
    return data.approval ?? null;
  } catch {
    return null;
  }
}

export async function createHITLApprovalRemote(params: {
  tool_name: string;
  title_id: string;
  description_id: string;
  risk_level?: "low" | "medium" | "high";
  target_path?: string;
}): Promise<HITLApprovalItem | null> {
  try {
    const res = await fetch(`${DEFAULT_BASE_URL}/api/v1/sandbox/approvals`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data.approval ?? null;
  } catch {
    return null;
  }
}

export async function fetchMCPServers(): Promise<MCPServerItem[] | null> {
  try {
    const res = await fetch(`${DEFAULT_BASE_URL}/api/v1/mcp/servers`);
    if (!res.ok) return null;
    const data = await res.json();
    return data.servers ?? null;
  } catch {
    return null;
  }
}

export async function toggleMCPServerRemote(
  serverId: string,
  enabled: boolean
): Promise<MCPServerItem | null> {
  try {
    const res = await fetch(
      `${DEFAULT_BASE_URL}/api/v1/mcp/servers/${serverId}/toggle`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled }),
      }
    );
    if (!res.ok) return null;
    const data = await res.json();
    return data.server ?? null;
  } catch {
    return null;
  }
}

export async function setEmergencyStopRemote(active: boolean): Promise<boolean> {
  try {
    const endpoint = active
      ? "/api/v1/computer-use/emergency-stop"
      : "/api/v1/computer-use/reset";
    const res = await fetch(`${DEFAULT_BASE_URL}${endpoint}`, {
      method: "POST",
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function fetchRAGDocuments(workspaceId?: string): Promise<any[] | null> {
  try {
    const url = workspaceId
      ? `${DEFAULT_BASE_URL}/api/v1/rag/documents?workspace_id=${workspaceId}`
      : `${DEFAULT_BASE_URL}/api/v1/rag/documents`;
    const res = await fetch(url);
    if (!res.ok) return null;
    const data = await res.json();
    return data.documents ?? null;
  } catch {
    return null;
  }
}

export async function indexWorkspaceFolderRemote(
  workspaceId: string,
  folderPath: string
): Promise<any | null> {
  try {
    const res = await fetch(`${DEFAULT_BASE_URL}/api/v1/rag/index-folder`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ workspace_id: workspaceId, folder_path: folderPath }),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function searchRAGRemote(query: string, workspaceId?: string): Promise<any[] | null> {
  try {
    const res = await fetch(`${DEFAULT_BASE_URL}/api/v1/rag/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, workspace_id: workspaceId }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data.results ?? null;
  } catch {
    return null;
  }
}

export async function fetchMemoriesRemote(query?: string): Promise<any[] | null> {
  try {
    const url = query
      ? `${DEFAULT_BASE_URL}/api/v1/memories?query=${encodeURIComponent(query)}`
      : `${DEFAULT_BASE_URL}/api/v1/memories`;
    const res = await fetch(url);
    if (!res.ok) return null;
    const data = await res.json();
    return data.memories ?? null;
  } catch {
    return null;
  }
}

export async function saveMemoryRemote(fact: string, category: string = "preferensi_pengguna"): Promise<any | null> {
  try {
    const res = await fetch(`${DEFAULT_BASE_URL}/api/v1/memories`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fact, category }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data.memory ?? null;
  } catch {
    return null;
  }
}

export async function fetchTelegramStatus(): Promise<any | null> {
  try {
    const res = await fetch(`${DEFAULT_BASE_URL}/api/v1/telegram/status`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function configureTelegramRemote(botToken: string): Promise<any | null> {
  try {
    const res = await fetch(`${DEFAULT_BASE_URL}/api/v1/telegram/configure`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bot_token: botToken }),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function regenerateTelegramCodeRemote(): Promise<string | null> {
  try {
    const res = await fetch(`${DEFAULT_BASE_URL}/api/v1/telegram/regenerate-code`, {
      method: "POST",
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data.pairing_code ?? null;
  } catch {
    return null;
  }
}

