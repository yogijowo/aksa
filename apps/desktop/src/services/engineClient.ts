import type {
  AgentNodeConfig,
  AgentTeam,
  EngineHealth,
  ExecutionStep,
  FileArtifact,
  HITLApprovalItem,
  MCPServerItem,
  ProviderStatusDetail,
  ProviderTokenStatus,
  WorkspaceFolder,
  WorkspaceFolderInspection,
} from "@/types/aksa";
import { apiFetch } from "./engineConnection";

export async function fetchEngineHealth(): Promise<EngineHealth> {
  try {
    const res = await apiFetch("/api/v1/health");
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
    const res = await apiFetch("/api/v1/tokens/analytics");
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function fetchConfiguredProviders(): Promise<Record<string, boolean> | null> {
  try {
    const res = await apiFetch("/api/v1/models/providers");
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
  maskedHints: Record<string, string>;
  providers: ProviderStatusDetail[];
} | null> {
  try {
    const res = await apiFetch("/api/v1/models/providers");
    if (!res.ok) return null;
    const data = await res.json();
    const configured: Record<string, boolean> = {};
    const maskedHints: Record<string, string> = {};
    const providers: ProviderStatusDetail[] = [];
    if (Array.isArray(data.providers)) {
      for (const p of data.providers) {
        const hasToken = Boolean(p.has_saved_token ?? p.configured);
        configured[p.id] = Boolean(p.configured);
        if (p.api_key_masked) {
          maskedHints[p.id] = String(p.api_key_masked);
        }
        providers.push({
          id: p.id,
          name: p.name,
          is_local: Boolean(p.is_local),
          configured: Boolean(p.configured),
          has_saved_token: hasToken,
          online: Boolean(p.online),
          token_status:
            (p.token_status as ProviderTokenStatus) ||
            (p.is_local
              ? p.online
                ? "connected"
                : "not_connected"
              : hasToken
              ? "token_saved"
              : "not_connected"),
          api_key_masked: p.api_key_masked ? String(p.api_key_masked) : undefined,
          last_test_ok: p.last_test_ok ?? null,
          last_tested_at: p.last_tested_at ?? null,
          last_test_message: p.last_test_message ?? null,
          installed_models: Array.isArray(p.installed_models)
            ? p.installed_models
            : Array.isArray(p.recommended_models)
            ? p.recommended_models
            : [],
        });
      }
    }
    return { configured, maskedHints, providers };
  } catch {
    return null;
  }
}

export async function fetchAgentTeams(): Promise<AgentTeam[] | null> {
  try {
    const res = await apiFetch("/api/v1/teams");
    if (!res.ok) return null;
    const data = await res.json();
    return data.teams ?? null;
  } catch {
    return null;
  }
}

export async function fetchWorkspaces(): Promise<WorkspaceFolder[] | null> {
  try {
    const res = await apiFetch("/api/v1/workspaces");
    if (!res.ok) return null;
    const data = await res.json();
    return data.workspaces ?? null;
  } catch {
    return null;
  }
}

export async function createAgentRemote(
  agent: Partial<AgentNodeConfig> & { team_id: string; name: string; role_title: string; description: string; provider: string; model_id: string; system_prompt: string }
): Promise<AgentNodeConfig | null> {
  try {
    const res = await apiFetch("/api/v1/agents", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(agent),
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data.agent ?? null;
  } catch {
    return null;
  }
}

export async function saveAgentUpdate(
  agentId: string,
  updates: Partial<AgentNodeConfig>
): Promise<AgentNodeConfig | null> {
  try {
    const res = await apiFetch(`/api/v1/agents/${agentId}`, {
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
    const res = await apiFetch(`/api/v1/agents/${agentId}`, {
      method: "DELETE",
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function saveProviderApiKey(provider: string, apiKey: string): Promise<boolean> {
  const trimmed = (apiKey || "").trim();
  if (!trimmed || trimmed.includes("••••") || trimmed.startsWith("****")) {
    return false;
  }
  try {
    const res = await apiFetch("/api/v1/models/keys", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider, api_key: trimmed }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function deleteProviderApiKeyRemote(provider: string): Promise<boolean> {
  try {
    const res = await apiFetch(`/api/v1/models/keys/${encodeURIComponent(provider)}`, {
      method: "DELETE",
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function testModelConnectionRemote(params: {
  provider: string;
  model_id: string;
}): Promise<{
  ok: boolean;
  token_status?: ProviderTokenStatus;
  reply?: string;
  simulated?: boolean;
  error?: string;
}> {
  try {
    const res = await apiFetch("/api/v1/models/test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      return {
        ok: false,
        token_status: "connection_failed",
        error: err.detail || "Gagal menghubungi layanan penyedia model.",
      };
    }
    const data = await res.json();
    const isOk = Boolean(data.ok) && !Boolean(data.simulated);
    return {
      ok: isOk,
      token_status:
        (data.token_status as ProviderTokenStatus) ||
        (isOk ? "connected" : "connection_failed"),
      reply: data.reply,
      simulated: Boolean(data.simulated),
      error: data.error || (!isOk ? data.reply : undefined),
    };
  } catch (err: any) {
    return {
      ok: false,
      token_status: "connection_failed",
      error: err?.message || "Tidak dapat terhubung ke layanan AKSA.",
    };
  }
}

export async function openNativeFolderPicker(options?: {
  title?: string;
  defaultPath?: string;
}): Promise<string | null> {
  try {
    const { open } = await import("@tauri-apps/plugin-dialog");
    const selected = await open({
      directory: true,
      multiple: false,
      title: options?.title || "Pilih Folder Ruang Kerja AKSA",
      defaultPath: options?.defaultPath,
    });
    if (typeof selected === "string" && selected.trim()) {
      return selected.trim();
    }
    if (Array.isArray(selected) && typeof selected[0] === "string" && selected[0].trim()) {
      return selected[0].trim();
    }
    return null;
  } catch {
    return null;
  }
}

export async function inspectWorkspacePathRemote(
  folderPath: string
): Promise<WorkspaceFolderInspection | null> {
  const trimmed = (folderPath || "").trim();
  if (!trimmed) return null;

  try {
    const res = await apiFetch("/api/v1/workspaces/inspect-path", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ folder_path: trimmed }),
    });
    if (res.ok) {
      return await res.json();
    }
  } catch {
    // Fallback to Tauri native Rust validation if sidecar is offline
  }

  try {
    const { invoke } = await import("@tauri-apps/api/core");
    const nativeRes = await invoke<{
      folder_path: string;
      name: string;
      folder_status: any;
      folder_status_label: string;
      is_valid_directory: boolean;
      readonly: boolean;
      recovery_hint: string | null;
    }>("validate_workspace_folder_native", { path: trimmed });
    if (nativeRes) {
      return {
        folder_path: nativeRes.folder_path,
        name: nativeRes.name,
        folder_status: nativeRes.folder_status,
        folder_status_label: nativeRes.folder_status_label,
        is_valid_directory: nativeRes.is_valid_directory,
        readable: nativeRes.is_valid_directory,
        writable: nativeRes.is_valid_directory && !nativeRes.readonly,
        recovery_hint: nativeRes.recovery_hint,
      };
    }
  } catch {
    // Running outside Tauri shell
  }

  return null;
}

export async function updateWorkspaceRemote(
  workspaceId: string,
  updates: {
    name?: string;
    allow_read?: boolean;
    allow_write?: boolean;
    allow_execute?: boolean;
    auto_rag_sync?: boolean;
    granular_permissions?: Record<string, boolean>;
  }
): Promise<WorkspaceFolder | null> {
  try {
    const res = await apiFetch(`/api/v1/workspaces/${encodeURIComponent(workspaceId)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updates),
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data.workspace ?? null;
  } catch {
    return null;
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
    const res = await apiFetch("/api/v1/workspaces", {
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
    const res = await apiFetch(`/api/v1/workspaces/${workspaceId}`, {
      method: "DELETE",
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function openFileInDefaultApp(filePath: string): Promise<boolean> {
  try {
    const res = await apiFetch("/api/v1/system/open-path", {
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
    const res = await apiFetch("/api/v1/orchestrate/execute", {
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
    const res = await apiFetch("/api/v1/sandbox/approvals");
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
    const res = await apiFetch(
      `/api/v1/sandbox/approvals/${requestId}/resolve`,
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
    const res = await apiFetch("/api/v1/sandbox/approvals", {
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
    const res = await apiFetch("/api/v1/mcp/servers");
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
    const res = await apiFetch(
      `/api/v1/mcp/servers/${serverId}/toggle`,
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
    const res = await apiFetch(endpoint, {
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
      ? `/api/v1/rag/documents?workspace_id=${workspaceId}`
      : "/api/v1/rag/documents";
    const res = await apiFetch(url);
    if (!res.ok) return null;
    const data = await res.json();
    return data.documents ?? null;
  } catch {
    return null;
  }
}

export async function deleteRAGDocumentRemote(documentId: string): Promise<boolean> {
  try {
    const res = await apiFetch(`/api/v1/rag/documents/${encodeURIComponent(documentId)}`, {
      method: "DELETE",
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function fetchSystemSettingsRemote(): Promise<Record<string, any> | null> {
  try {
    const res = await apiFetch("/api/v1/system/settings");
    if (!res.ok) return null;
    const data = await res.json();
    return data.settings ?? null;
  } catch {
    return null;
  }
}

export async function saveSystemSettingRemote(key: string, value: unknown): Promise<boolean> {
  try {
    const res = await apiFetch("/api/v1/system/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key, value }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function updatePrivacySettingsRemote(payload: {
  provider_mode?: string;
  default_classification?: string;
  telemetry_opt_in?: boolean;
}): Promise<boolean> {
  try {
    const res = await apiFetch("/api/v1/privacy/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function indexWorkspaceFolderRemote(
  workspaceId: string,
  folderPath: string
): Promise<any | null> {
  try {
    const res = await apiFetch("/api/v1/rag/index-folder", {
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
    const res = await apiFetch("/api/v1/rag/search", {
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
      ? `/api/v1/memories?query=${encodeURIComponent(query)}`
      : "/api/v1/memories";
    const res = await apiFetch(url);
    if (!res.ok) return null;
    const data = await res.json();
    return data.memories ?? null;
  } catch {
    return null;
  }
}

export async function saveMemoryRemote(fact: string, category: string = "preferensi_pengguna"): Promise<any | null> {
  try {
    const res = await apiFetch("/api/v1/memories", {
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
    const res = await apiFetch("/api/v1/telegram/status");
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function configureTelegramRemote(botToken: string): Promise<any | null> {
  try {
    const res = await apiFetch("/api/v1/telegram/configure", {
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
    const res = await apiFetch("/api/v1/telegram/regenerate-code", {
      method: "POST",
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data.pairing_code ?? null;
  } catch {
    return null;
  }
}

// --- Desktop Applications API ---
export async function fetchDesktopAppsRemote(): Promise<any[] | null> {
  try {
    const res = await apiFetch("/api/v1/system/apps");
    if (!res.ok) return null;
    const data = await res.json();
    return data.apps ?? [];
  } catch {
    return null;
  }
}

export async function refreshDesktopAppsRemote(): Promise<any[] | null> {
  try {
    const res = await apiFetch("/api/v1/system/apps/refresh", { method: "POST" });
    if (!res.ok) return null;
    const data = await res.json();
    return data.apps ?? [];
  } catch {
    return null;
  }
}

export async function launchDesktopAppRemote(appId: string, documentPath?: string): Promise<{ success: boolean; message: string }> {
  try {
    const res = await apiFetch(`/api/v1/system/apps/${encodeURIComponent(appId)}/launch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ document_path: documentPath }),
    });
    return await res.json();
  } catch (err: any) {
    return { success: false, message: String(err?.message || err) };
  }
}

export async function toggleDesktopAppConnectionRemote(
  appId: string,
  isConnected: boolean
): Promise<{ success: boolean; app?: any; is_connected?: boolean; message?: string } | null> {
  try {
    const res = await apiFetch(`/api/v1/system/apps/${encodeURIComponent(appId)}/toggle-connection`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_connected: isConnected }),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

// --- OS Permissions & Security Broker API ---
export async function fetchSystemPermissionsRemote(workspaceFolder?: string): Promise<any[] | null> {
  try {
    const url = workspaceFolder
      ? `/api/v1/system/permissions?workspace_folder=${encodeURIComponent(workspaceFolder)}`
      : "/api/v1/system/permissions";
    const res = await apiFetch(url);
    if (!res.ok) return null;
    const data = await res.json();
    return data.capabilities ?? [];
  } catch {
    return null;
  }
}

export async function requestSystemPermissionRemote(capabilityId: string, resourceScope: string = "workspace"): Promise<any | null> {
  try {
    const res = await apiFetch("/api/v1/system/permissions/request", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ capability_id: capabilityId, resource_scope: resourceScope }),
    });
    return await res.json();
  } catch {
    return null;
  }
}

export async function revokeSystemPermissionRemote(grantId: string): Promise<boolean> {
  try {
    const res = await apiFetch(`/api/v1/system/permissions/${encodeURIComponent(grantId)}`, {
      method: "DELETE",
    });
    return res.ok;
  } catch {
    return false;
  }
}

// --- Agent Skills Manager API ---
export async function fetchSkillsRemote(): Promise<{ installed_skills: any[]; curated_catalog: any[] } | null> {
  try {
    const res = await apiFetch("/api/v1/skills");
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function installCuratedSkillRemote(skillId: string): Promise<any | null> {
  try {
    const res = await apiFetch("/api/v1/skills/install-curated", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ skill_id: skillId }),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function toggleSkillStatusRemote(skillId: string, enabled: boolean): Promise<any | null> {
  try {
    const res = await apiFetch(`/api/v1/skills/${encodeURIComponent(skillId)}/toggle`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled }),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function deleteSkillRemote(skillId: string): Promise<boolean> {
  try {
    const res = await apiFetch(`/api/v1/skills/${encodeURIComponent(skillId)}`, {
      method: "DELETE",
    });
    return res.ok;
  } catch {
    return false;
  }
}

// --- Root Directory, Agent Learning & Dynamic Models API ---
export async function fetchRootDirStatusRemote(): Promise<any | null> {
  try {
    const res = await apiFetch("/api/v1/system/root-dir");
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function setRootDirRemote(rootPath: string): Promise<any | null> {
  try {
    const res = await apiFetch("/api/v1/system/root-dir", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ root_path: rootPath }),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function fetchDiscoveredModelsRemote(): Promise<any | null> {
  try {
    const res = await apiFetch("/api/v1/models/discovered");
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function refreshDiscoveredModelsRemote(providerId?: string): Promise<any | null> {
  try {
    const url = providerId
      ? `/api/v1/models/providers/${encodeURIComponent(providerId)}/refresh`
      : "/api/v1/models/refresh";
    const res = await apiFetch(url, { method: "POST" });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function fetchAgentMetricsRemote(agentId: string): Promise<any | null> {
  try {
    const res = await apiFetch(`/api/v1/agents/${encodeURIComponent(agentId)}/metrics`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function fetchAgentMemoryRemote(agentId: string): Promise<any | null> {
  try {
    const res = await apiFetch(`/api/v1/agents/${encodeURIComponent(agentId)}/memory`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function fetchAgentCandidateSkillsRemote(agentId: string): Promise<any | null> {
  try {
    const res = await apiFetch(`/api/v1/agents/${encodeURIComponent(agentId)}/skills/candidates`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function promoteCandidateSkillRemote(
  agentId: string,
  skillId: string,
  version: string = "1.0.0",
  promoteToShared: boolean = false
): Promise<any | null> {
  try {
    const res = await apiFetch(`/api/v1/agents/${encodeURIComponent(agentId)}/skills/${encodeURIComponent(skillId)}/promote`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ version, promote_to_shared: promoteToShared }),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}



