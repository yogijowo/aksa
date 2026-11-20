import { create } from "zustand";
import type {
  AgentNodeConfig,
  AgentTeam,
  ChatMessage,
  ChatSessionItem,
  EngineHealth,
  ExecutionStep,
  FileArtifact,
  HITLApprovalItem,
  MCPServerItem,
  NavSection,
  ResolvedTheme,
  ThemeMode,
  UIDensityMode,
  WorkspaceFolder,
} from "@/types/aksa";
import {
  createAgentRemote,
  createHITLApprovalRemote,
  createWorkspaceRemote,
  deleteAgentRemote,
  deleteSystemSettingRemote,
  deleteWorkspaceRemote,
  executeTaskOnEngine,
  fetchAgentTeams,
  fetchEngineHealth,
  fetchHITLApprovals,
  fetchMCPServers,
  fetchSystemSettingsRemote,
  fetchTokenAnalytics,
  fetchWorkspaces,
  resolveHITLApprovalRemote,
  saveAgentUpdate,
  saveSystemSettingRemote,
  setEmergencyStopRemote,
  toggleMCPServerRemote,
  updateWorkspaceRemote,
} from "@/services/engineClient";
import {
  computeAutoHierarchyLayout,
  extractFolderDisplayName,
  wouldCreateAgentCycle,
} from "@/lib/utils";

const INITIAL_INDONESIAN_TEAM: AgentTeam = {
  id: "team_nusantara_default",
  name: "Tim Produktivitas Kantor Indonesia",
  description:
    "Tim asisten bertingkat siap pakai untuk pengolahan dokumen Office, pencarian referensi dokumen, dan automasi komputer.",
  is_default: true,
  agents: [
    {
      id: "agt_supervisor_utama",
      team_id: "team_nusantara_default",
      parent_id: null,
      name: "Manajer Eksekutif",
      role_title: "Koordinator Utama (Asisten Utama)",
      description:
        "Menerima instruksi pengguna, menyusun rencana kerja bertahap, mendelegasikan tugas ke agen pendukung spesialis, dan merangkum hasil akhir.",
      avatar_icon: "brain-circuit",
      tier_level: 0,
      provider: "gemini",
      model_id: "gemini-4-carbon",
      model_selection_mode: "auto",
      temperature: 0.2,
      max_tokens: 4096,
      system_prompt:
        "Anda adalah Manajer Eksekutif AKSA yang memimpin tim agen pendukung spesialis. Pahami instruksi pengguna dalam Bahasa Indonesia, bagi tugas secara hemat kuota, dan pastikan hasil akhir rapi.",
      tool_categories: ["delegation", "filesystem"],
      position_x: 460,
      position_y: 30,
    },
    {
      id: "agt_spesialis_office",
      team_id: "team_nusantara_default",
      parent_id: "agt_supervisor_utama",
      name: "Spesialis Administrasi & Office",
      role_title: "Agen Pembuat Word, Excel, PPT & PDF",
      description:
        "Ahli membuat dan merapikan file Microsoft Excel (.xlsx dengan rumus & grafik), Word (.docx surat resmi & laporan), PowerPoint (.pptx), dan PDF di dalam Folder Kerja.",
      avatar_icon: "file-spreadsheet",
      tier_level: 1,
      provider: "deepseek",
      model_id: "deepseek-chat",
      model_selection_mode: "auto",
      temperature: 0.1,
      max_tokens: 4096,
      system_prompt:
        "Anda adalah Spesialis Administrasi & Microsoft Office. Buat file Excel (.xlsx lengkap dengan rumus SUM/VLOOKUP dan format Rupiah), Word (.docx), PowerPoint (.pptx), dan PDF.",
      tool_categories: ["office_excel", "office_word", "office_ppt", "pdf_tools", "filesystem"],
      position_x: 40,
      position_y: 360,
    },
    {
      id: "agt_peneliti_rag",
      team_id: "team_nusantara_default",
      parent_id: "agt_supervisor_utama",
      name: "Peneliti Dokumen & Arsip",
      role_title: "Agen Pencarian & Ringkasan Dokumen Lokal",
      description:
        "Mencari informasi akurat dan kutipan penting dari koleksi dokumen di Pengetahuan AKSA secara cepat dan hemat kuota.",
      avatar_icon: "book-open-check",
      tier_level: 1,
      provider: "ollama",
      model_id: "qwen3.8:8b",
      model_selection_mode: "auto",
      temperature: 0.1,
      max_tokens: 2048,
      system_prompt:
        "Anda adalah Peneliti Dokumen & Arsip lokal. Ekstrak fakta, angka, dan kutipan halaman dari dokumen di Folder Kerja secara ringkas.",
      tool_categories: ["rag_search", "filesystem", "pdf_tools"],
      position_x: 460,
      position_y: 360,
    },
    {
      id: "agt_operator_pc",
      team_id: "team_nusantara_default",
      parent_id: "agt_supervisor_utama",
      name: "Operator PC & Automasi Sistem",
      role_title: "Agen Kontrol Aplikasi, Skrip Data & Layar",
      description:
        "Membantu mengoperasikan aplikasi komputer yang diizinkan, menjalankan pemrosesan data otomatis, dan kontrol layar visual atas persetujuan Anda.",
      avatar_icon: "monitor-cog",
      tier_level: 1,
      provider: "anthropic",
      model_id: "claude-sonnet-5-5",
      model_selection_mode: "auto",
      temperature: 0.1,
      max_tokens: 4096,
      system_prompt:
        "Anda adalah Operator PC & Automasi Sistem. Jalankan automasi aplikasi desktop, skrip pemrosesan data terisolasi, dan kontrol visual di bawah izin keamanan pengguna.",
      tool_categories: ["os_automation", "uv_python", "computer_use", "filesystem"],
      position_x: 880,
      position_y: 360,
    },
  ],
};

const getSavedStorage = (key: string, fallback: string): string => {
  if (typeof window !== "undefined") {
    try {
      const val = localStorage.getItem(key);
      if (val) return val;
    } catch {}
  }
  return fallback;
};

const getSystemPrefersDark = (): boolean => {
  if (typeof window !== "undefined" && typeof window.matchMedia === "function") {
    try {
      return window.matchMedia("(prefers-color-scheme: dark)").matches;
    } catch {}
  }
  return true;
};

const getSystemPrefersReducedMotion = (): boolean => {
  if (typeof window !== "undefined" && typeof window.matchMedia === "function") {
    try {
      return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    } catch {}
  }
  return false;
};

const resolveEffectiveTheme = (mode: ThemeMode, osPrefersDark: boolean): ResolvedTheme => {
  if (mode === "light") return "light";
  if (mode === "dark") return "dark";
  return osPrefersDark ? "dark" : "light";
};

const INITIAL_THEME_MODE = (getSavedStorage("aksa_theme_mode", "dark") as ThemeMode) || "dark";
const INITIAL_RESOLVED_THEME = resolveEffectiveTheme(INITIAL_THEME_MODE, getSystemPrefersDark());
const INITIAL_UI_DENSITY =
  (getSavedStorage("aksa_ui_density", "comfortable") as UIDensityMode) || "comfortable";
const INITIAL_REDUCED_MOTION =
  getSavedStorage("aksa_reduced_motion", "") === "true"
    ? true
    : getSavedStorage("aksa_reduced_motion", "") === "false"
    ? false
    : getSystemPrefersReducedMotion();

const INITIAL_WORKSPACES: WorkspaceFolder[] = [];
const INITIAL_ARTIFACTS: FileArtifact[] = [];
const INITIAL_MESSAGES: ChatMessage[] = [];

interface AksaState {
  activeNav: NavSection;
  isSidebarCollapsed: boolean;
  isArtifactDrawerOpen: boolean;
  isSessionHistoryOpen: boolean;
  savedSessions: ChatSessionItem[];
  themeMode: ThemeMode;
  resolvedTheme: ResolvedTheme;
  uiDensity: UIDensityMode;
  reducedMotion: boolean;
  engineHealth: EngineHealth;
  teams: AgentTeam[];
  activeTeamId: string;
  selectedAgentId: string | null;
  workspaces: WorkspaceFolder[];
  activeWorkspaceId: string;
  messages: ChatMessage[];
  artifacts: FileArtifact[];
  totalTokensUsed: number;
  totalTokensSaved: number;
  pendingApprovals: HITLApprovalItem[];
  mcpServers: MCPServerItem[];
  emergencyStopActive: boolean;

  // Initial application & database hydration tracking
  isAppReady: boolean;
  initStepLabel: string;
  initProgress: number;
  initStage: {
    engine: "pending" | "loading" | "done" | "error";
    database: "pending" | "loading" | "done" | "error";
    workspace: "pending" | "loading" | "done" | "error";
  };
  setAppReady: (ready: boolean) => void;

  // Real-time execution tracking
  isExecuting: boolean;
  activeAgentId: string | null;
  activeAgentStep: string | null;
  liveExecutionSteps: ExecutionStep[];

  setActiveNav: (nav: NavSection) => void;
  toggleSidebar: () => void;
  setArtifactDrawerOpen: (open: boolean) => void;
  setSessionHistoryOpen: (open: boolean) => void;
  loadSavedSessions: () => Promise<void>;
  switchChatSession: (sessionId: string) => Promise<void>;
  deleteChatSession: (sessionId: string) => Promise<void>;
  setThemeMode: (mode: ThemeMode) => void;
  syncSystemTheme: (osPrefersDark: boolean) => void;
  setUiDensity: (density: UIDensityMode) => void;
  setReducedMotion: (reduced: boolean) => void;
  selectAgent: (agentId: string | null) => void;
  setActiveWorkspace: (workspaceId: string) => void;
  addWorkspaceFolder: (
    folderPath: string,
    name?: string,
    permissions?: {
      allow_read?: boolean;
      allow_write?: boolean;
      allow_execute?: boolean;
    }
  ) => Promise<WorkspaceFolder>;
  removeWorkspaceFolder: (workspaceId: string) => Promise<void>;
  updateWorkspacePermissions: (
    workspaceId: string,
    updates: Partial<
      Pick<
        WorkspaceFolder,
        "allow_read" | "allow_write" | "allow_execute" | "granular_permissions"
      >
    >
  ) => void;
  updateAgentConfig: (agentId: string, updates: Partial<AgentNodeConfig>) => Promise<void>;
  addSubAgent: (
    parentAgent: AgentNodeConfig,
    customOptions?: Partial<AgentNodeConfig>
  ) => Promise<AgentNodeConfig>;
  reparentAgent: (
    agentId: string,
    newParentId: string
  ) => Promise<{ ok: boolean; error?: string }>;
  autoLayoutAgents: () => Promise<void>;
  deleteAgentNode: (agentId: string) => Promise<void>;
  sendUserPrompt: (promptText: string) => Promise<void>;
  startNewChatSession: () => Promise<void>;
  requestSampleApproval: () => Promise<void>;
  resolveApproval: (requestId: string, approved: boolean) => Promise<void>;
  toggleMcpServer: (serverId: string, enabled: boolean) => Promise<void>;
  toggleEmergencyStop: (active: boolean) => Promise<void>;
  syncWithBackendEngine: () => Promise<void>;
}

export const useAksaStore = create<AksaState>((set, get) => ({
  activeNav: getSavedStorage("aksa_active_nav", "ruang_kerja") as NavSection,
  isSidebarCollapsed: false,
  isArtifactDrawerOpen: false,
  isSessionHistoryOpen: false,
  savedSessions: [],
  themeMode: INITIAL_THEME_MODE,
  resolvedTheme: INITIAL_RESOLVED_THEME,
  uiDensity: INITIAL_UI_DENSITY,
  reducedMotion: INITIAL_REDUCED_MOTION,
  engineHealth: {
    online: true,
    version: "1.0.0",
    ollama_online: false,
    ollama_models: [],
    telegram_connected: false,
    telegram_bot_username: null,
  },
  teams: [INITIAL_INDONESIAN_TEAM],
  activeTeamId: getSavedStorage("aksa_active_team_id", INITIAL_INDONESIAN_TEAM.id),
  selectedAgentId: "agt_supervisor_utama",
  workspaces: INITIAL_WORKSPACES,
  activeWorkspaceId: getSavedStorage("aksa_active_workspace_id", ""),
  messages: INITIAL_MESSAGES,
  artifacts: INITIAL_ARTIFACTS,
  totalTokensUsed: 0,
  totalTokensSaved: 0,
  pendingApprovals: [],
  isExecuting: false,
  activeAgentId: null,
  activeAgentStep: null,
  liveExecutionSteps: [],
  mcpServers: [
    {
      id: "mcp_filesystem",
      name: "Filesystem MCP Server",
      transport: "stdio",
      command: "npx",
      args: ["-y", "@modelcontextprotocol/server-filesystem"],
      enabled: true,
      description_id: "Akses standar untuk membaca struktur folder dan file di ruang kerja.",
      discovered_tools: ["read_file", "write_file", "list_directory"],
    },
    {
      id: "mcp_playwright",
      name: "Playwright Browser Automation MCP",
      transport: "stdio",
      command: "npx",
      args: ["-y", "@executeautomation/playwright-mcp-server"],
      enabled: false,
      description_id: "Automasi peramban web untuk mengisi formulir dan mengunduh laporan.",
      discovered_tools: ["playwright_navigate", "playwright_click", "playwright_screenshot"],
    },
    {
      id: "mcp_sqlite",
      name: "SQLite / Database Explorer MCP",
      transport: "stdio",
      command: "uvx",
      args: ["mcp-server-sqlite"],
      enabled: true,
      description_id: "Pencarian dan analisis tabel basis data lokal di komputer Anda.",
      discovered_tools: ["read_query", "list_tables", "describe_table"],
    },
  ],
  emergencyStopActive: false,

  isAppReady: false,
  initStepLabel: "Menghubungkan ke Mesin & Basis Data AKSA...",
  initProgress: 15,
  initStage: {
    engine: "loading",
    database: "pending",
    workspace: "pending",
  },
  setAppReady: (ready) => set({ isAppReady: ready }),

  setActiveNav: (nav) => {
    if (typeof window !== "undefined") {
      try {
        localStorage.setItem("aksa_active_nav", nav);
      } catch {}
    }
    set({ activeNav: nav });
  },
  toggleSidebar: () => set((state) => ({ isSidebarCollapsed: !state.isSidebarCollapsed })),
  setArtifactDrawerOpen: (open) => set({ isArtifactDrawerOpen: open }),
  setSessionHistoryOpen: (open) => set({ isSessionHistoryOpen: open }),

  loadSavedSessions: async () => {
    try {
      const settings = await fetchSystemSettingsRemote();
      if (!settings) return;
      const sessions: ChatSessionItem[] = [];
      for (const [key, val] of Object.entries(settings)) {
        if (key.startsWith("chat_session_") && val && typeof val === "object") {
          const sVal = val as Record<string, unknown>;
          const msgs = Array.isArray(sVal.messages) ? (sVal.messages as ChatMessage[]) : [];
          if (msgs.length === 0) continue;
          const firstUserMsg = msgs.find((m) => m.sender_role === "user");
          const title = firstUserMsg ? firstUserMsg.content.slice(0, 48) : "Sesi Percakapan";
          const rawTime = typeof sVal.timestamp === "string" ? sVal.timestamp : null;
          const dateObj = rawTime
            ? new Date(rawTime)
            : new Date(Number(key.replace("chat_session_", "")) || Date.now());
          const formattedDate = dateObj.toLocaleDateString("id-ID", {
            day: "numeric",
            month: "short",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit",
          });
          sessions.push({
            id: key,
            key,
            title,
            timestamp: rawTime || dateObj.toISOString(),
            formatted_date: formattedDate,
            message_count: msgs.length,
            artifact_count: msgs.reduce((acc, m) => acc + (m.artifacts?.length || 0), 0),
            workspace_id: typeof sVal.workspace_id === "string" ? sVal.workspace_id : undefined,
            messages: msgs,
          });
        }
      }
      sessions.sort(
        (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
      );
      set({ savedSessions: sessions });
    } catch (err) {
      console.warn("Gagal memuat riwayat sesi percakapan:", err);
    }
  },

  switchChatSession: async (sessionId: string) => {
    const session = get().savedSessions.find((s) => s.id === sessionId);
    if (!session) return;
    const currentMessages = get().messages;
    if (currentMessages.length > 0) {
      const archiveKey = `chat_session_${Date.now()}`;
      try {
        await saveSystemSettingRemote(archiveKey, {
          timestamp: new Date().toISOString(),
          messages: currentMessages,
          workspace_id: get().activeWorkspaceId,
        });
      } catch (err) {
        console.warn("Gagal mengarsipkan sesi saat ini:", err);
      }
    }
    set({
      messages: session.messages,
      activeWorkspaceId: session.workspace_id || get().activeWorkspaceId,
      liveExecutionSteps: [],
      activeAgentStep: null,
      activeAgentId: null,
    });
    void saveSystemSettingRemote("workspace_chat_state", {
      messages: session.messages.slice(-40),
      artifacts: get().artifacts.slice(0, 40),
    });
    await get().loadSavedSessions();
  },

  deleteChatSession: async (sessionId: string) => {
    await deleteSystemSettingRemote(sessionId);
    set((state) => ({
      savedSessions: state.savedSessions.filter((s) => s.id !== sessionId),
    }));
  },

  setThemeMode: (mode) => {
    const resolved = resolveEffectiveTheme(mode, getSystemPrefersDark());
    if (typeof window !== "undefined") {
      try {
        localStorage.setItem("aksa_theme_mode", mode);
      } catch {}
    }
    if (typeof document !== "undefined") {
      document.documentElement.setAttribute("data-theme", resolved);
    }
    set({ themeMode: mode, resolvedTheme: resolved });
    void saveSystemSettingRemote("theme_mode", mode);
  },

  syncSystemTheme: (osPrefersDark) => {
    const currentMode = get().themeMode;
    if (currentMode === "system") {
      const resolved: ResolvedTheme = osPrefersDark ? "dark" : "light";
      if (typeof document !== "undefined") {
        document.documentElement.setAttribute("data-theme", resolved);
      }
      set({ resolvedTheme: resolved });
    }
  },

  setUiDensity: (density) => {
    if (typeof window !== "undefined") {
      try {
        localStorage.setItem("aksa_ui_density", density);
      } catch {}
    }
    if (typeof document !== "undefined") {
      document.documentElement.setAttribute("data-density", density);
    }
    set({ uiDensity: density });
    void saveSystemSettingRemote("ui_density", density);
  },

  setReducedMotion: (reduced) => {
    if (typeof window !== "undefined") {
      try {
        localStorage.setItem("aksa_reduced_motion", String(reduced));
      } catch {}
    }
    if (typeof document !== "undefined") {
      document.documentElement.setAttribute("data-reduce-motion", String(reduced));
    }
    set({ reducedMotion: reduced });
    void saveSystemSettingRemote("reduced_motion", reduced);
  },

  selectAgent: (agentId) => {
    set({ selectedAgentId: agentId });
    if (agentId) {
      void saveSystemSettingRemote("selected_agent_id", agentId);
    }
  },

  setActiveWorkspace: (workspaceId) => {
    if (typeof window !== "undefined") {
      try {
        localStorage.setItem("aksa_active_workspace_id", workspaceId);
      } catch {}
    }
    set({ activeWorkspaceId: workspaceId });
    void saveSystemSettingRemote("active_workspace_id", workspaceId);
  },

  addWorkspaceFolder: async (folderPath, name, permissions) => {
    const cleanName = extractFolderDisplayName(folderPath, name);
    const allowRead = permissions?.allow_read ?? true;
    const allowWrite = permissions?.allow_write ?? true;
    // Mandatory security rule (Section 6): Selecting a folder never enables execute automatically
    const allowExecute = permissions?.allow_execute ?? false;

    const remote = await createWorkspaceRemote({
      name: cleanName,
      folder_path: folderPath,
      allow_read: allowRead,
      allow_write: allowWrite,
      allow_execute: allowExecute,
    });
    const newWs: WorkspaceFolder = remote || {
      id: `ws_${Date.now()}`,
      name: cleanName,
      folder_path: folderPath,
      allow_read: allowRead,
      allow_write: allowWrite,
      allow_execute: allowExecute,
      auto_rag_sync: true,
      folder_status: "accessible",
      folder_status_label: "Dapat diakses",
      last_indexed_at: "Baru ditambahkan • Siap digunakan",
      granular_permissions: {
        list_files: allowRead,
        read_content: allowRead,
        create_files: allowWrite,
        modify_files: allowWrite,
        move_files: allowWrite,
        delete_files: false,
        execute_programs: allowExecute,
      },
    };
    if (typeof window !== "undefined") {
      try {
        localStorage.setItem("aksa_active_workspace_id", newWs.id);
      } catch {}
    }
    set((state) => ({
      workspaces: [newWs, ...state.workspaces.filter((w) => w.folder_path !== folderPath)],
      activeWorkspaceId: newWs.id,
    }));
    void saveSystemSettingRemote("active_workspace_id", newWs.id);
    return newWs;
  },

  removeWorkspaceFolder: async (workspaceId) => {
    await deleteWorkspaceRemote(workspaceId);
    set((state) => {
      const remaining = state.workspaces.filter((w) => w.id !== workspaceId);
      const nextActiveId =
        state.activeWorkspaceId === workspaceId
          ? (remaining[0]?.id ?? "")
          : state.activeWorkspaceId;
      if (typeof window !== "undefined") {
        try {
          localStorage.setItem("aksa_active_workspace_id", nextActiveId);
        } catch {}
      }
      void saveSystemSettingRemote("active_workspace_id", nextActiveId);
      return {
        workspaces: remaining,
        activeWorkspaceId: nextActiveId,
      };
    });
  },

  updateWorkspacePermissions: (workspaceId, updates) => {
    let computedRead = true;
    let computedWrite = true;
    let computedExec = false;
    let computedGranular: Record<string, boolean> | undefined;

    set((state) => ({
      workspaces: state.workspaces.map((ws) => {
        if (ws.id !== workspaceId) return ws;
        const baseGranular = ws.granular_permissions ?? {
          list_files: ws.allow_read,
          read_content: ws.allow_read,
          create_files: ws.allow_write,
          modify_files: ws.allow_write,
          move_files: ws.allow_write,
          delete_files: false,
          execute_programs: ws.allow_execute,
        };
        const mergedGranular = updates.granular_permissions
          ? { ...baseGranular, ...updates.granular_permissions }
          : {
              ...baseGranular,
              ...(updates.allow_read !== undefined
                ? { list_files: updates.allow_read, read_content: updates.allow_read }
                : {}),
              ...(updates.allow_write !== undefined
                ? {
                    create_files: updates.allow_write,
                    modify_files: updates.allow_write,
                    move_files: updates.allow_write,
                  }
                : {}),
              ...(updates.allow_execute !== undefined
                ? { execute_programs: updates.allow_execute }
                : {}),
            };
        const nextRead =
          updates.allow_read !== undefined
            ? updates.allow_read
            : mergedGranular.list_files || mergedGranular.read_content;
        const nextWrite =
          updates.allow_write !== undefined
            ? updates.allow_write
            : mergedGranular.create_files ||
              mergedGranular.modify_files ||
              mergedGranular.move_files ||
              mergedGranular.delete_files;
        const nextExec =
          updates.allow_execute !== undefined
            ? updates.allow_execute
            : mergedGranular.execute_programs;

        computedRead = nextRead;
        computedWrite = nextWrite;
        computedExec = nextExec;
        computedGranular = mergedGranular;

        return {
          ...ws,
          ...updates,
          allow_read: nextRead,
          allow_write: nextWrite,
          allow_execute: nextExec,
          granular_permissions: mergedGranular,
        };
      }),
    }));

    void updateWorkspaceRemote(workspaceId, {
      allow_read: computedRead,
      allow_write: computedWrite,
      allow_execute: computedExec,
      granular_permissions: computedGranular,
    });
  },

  updateAgentConfig: async (agentId, updates) => {
    set((state) => ({
      teams: state.teams.map((team) => ({
        ...team,
        agents: team.agents.map((agt) => (agt.id === agentId ? { ...agt, ...updates } : agt)),
      })),
    }));
    await saveAgentUpdate(agentId, updates);
  },

  addSubAgent: async (parentAgent, customOptions) => {
    const activeTeam =
      get().teams.find((t) => t.id === parentAgent.team_id) ?? get().teams[0];
    const siblings =
      activeTeam?.agents.filter((a) => a.parent_id === parentAgent.id) ?? [];
    const offsetIndex = siblings.length;
    const newId = `agt_${Date.now().toString(36)}`;
    const newAgent: AgentNodeConfig = {
      id: newId,
      team_id: parentAgent.team_id,
      parent_id: parentAgent.id,
      name: customOptions?.name || "Agen Pendukung Baru",
      role_title: customOptions?.role_title || "Agen Pendukung Khusus",
      description:
        customOptions?.description ||
        "Membantu menyelesaikan tugas tertentu secara terfokus sesuai kemampuan yang Anda pilih.",
      avatar_icon: customOptions?.avatar_icon || "bot",
      tier_level: parentAgent.tier_level + 1,
      provider: customOptions?.provider || "ollama",
      model_id: customOptions?.model_id || "qwen3.8:8b",
      model_selection_mode: customOptions?.model_selection_mode || "auto",
      temperature: customOptions?.temperature ?? 0.2,
      max_tokens: customOptions?.max_tokens ?? 2048,
      system_prompt:
        customOptions?.system_prompt ||
        "Anda adalah Agen Pendukung di dalam tim AKSA. Kerjakan instruksi secara akurat dan berikan ringkasan hasil yang jelas.",
      // Mandatory security rule: new agents start with basic safe filesystem capability, never inheriting full parent privileges
      tool_categories: customOptions?.tool_categories || ["filesystem"],
      position_x: Math.max(40, parentAgent.position_x + (offsetIndex - 1) * 420),
      position_y: parentAgent.position_y + 330,
    };

    set((state) => ({
      teams: state.teams.map((team) =>
        team.id === parentAgent.team_id
          ? { ...team, agents: [...team.agents, newAgent] }
          : team
      ),
      selectedAgentId: newId,
    }));

    const remoteCreated = await createAgentRemote(newAgent);
    if (remoteCreated && remoteCreated.id !== newId) {
      set((state) => ({
        teams: state.teams.map((team) =>
          team.id === parentAgent.team_id
            ? {
                ...team,
                agents: team.agents.map((a) => (a.id === newId ? remoteCreated : a)),
              }
            : team
        ),
        selectedAgentId: remoteCreated.id,
      }));
      return remoteCreated;
    }
    return newAgent;
  },

  reparentAgent: async (agentId, newParentId) => {
    const activeTeam =
      get().teams.find((t) => t.id === get().activeTeamId) ?? get().teams[0];
    if (!activeTeam) {
      return { ok: false, error: "Tim aktif tidak ditemukan." };
    }

    const targetAgent = activeTeam.agents.find((a) => a.id === agentId);
    const parentAgent = activeTeam.agents.find((a) => a.id === newParentId);

    if (!targetAgent || !parentAgent) {
      return { ok: false, error: "Agen atau agen induk tidak ditemukan." };
    }
    if (targetAgent.parent_id === null) {
      return {
        ok: false,
        error: "Koordinator Utama (root) memimpin tim dan tidak dapat dijadikan sub-agen.",
      };
    }
    if (wouldCreateAgentCycle(activeTeam.agents, agentId, newParentId)) {
      return {
        ok: false,
        error:
          "Relasi melingkar (circular dependency) ditolak: Agen induk tidak boleh berada di bawah sub-agen ini.",
      };
    }

    const updatedTemp = activeTeam.agents.map((a) =>
      a.id === agentId ? { ...a, parent_id: newParentId } : a
    );
    const layoutMap = computeAutoHierarchyLayout(updatedTemp);

    set((state) => ({
      teams: state.teams.map((team) =>
        team.id !== activeTeam.id
          ? team
          : {
              ...team,
              agents: team.agents.map((a) => {
                const l = layoutMap[a.id];
                if (a.id === agentId) {
                  return {
                    ...a,
                    parent_id: newParentId,
                    tier_level: l ? l.tier_level : parentAgent.tier_level + 1,
                    position_x: l ? l.position_x : a.position_x,
                    position_y: l ? l.position_y : a.position_y,
                  };
                }
                return l ? { ...a, tier_level: l.tier_level } : a;
              }),
            }
      ),
    }));

    const newTier = layoutMap[agentId]?.tier_level ?? parentAgent.tier_level + 1;
    await saveAgentUpdate(agentId, {
      parent_id: newParentId,
      tier_level: newTier,
      position_x: layoutMap[agentId]?.position_x,
      position_y: layoutMap[agentId]?.position_y,
    });
    for (const agt of activeTeam.agents) {
      if (agt.id === agentId) continue;
      const l = layoutMap[agt.id];
      if (l) {
        void saveAgentUpdate(agt.id, {
          tier_level: l.tier_level,
          position_x: l.position_x,
          position_y: l.position_y,
        });
      }
    }
    return { ok: true };
  },

  autoLayoutAgents: async () => {
    const activeTeam =
      get().teams.find((t) => t.id === get().activeTeamId) ?? get().teams[0];
    if (!activeTeam) return;

    const layoutMap = computeAutoHierarchyLayout(activeTeam.agents);
    set((state) => ({
      teams: state.teams.map((team) =>
        team.id !== activeTeam.id
          ? team
          : {
              ...team,
              agents: team.agents.map((a) => {
                const l = layoutMap[a.id];
                return l
                  ? {
                      ...a,
                      position_x: l.position_x,
                      position_y: l.position_y,
                      tier_level: l.tier_level,
                    }
                  : a;
              }),
            }
      ),
    }));

    for (const agt of activeTeam.agents) {
      const l = layoutMap[agt.id];
      if (l) {
        void saveAgentUpdate(agt.id, {
          position_x: l.position_x,
          position_y: l.position_y,
          tier_level: l.tier_level,
        });
      }
    }
  },

  deleteAgentNode: async (agentId) => {
    const activeTeam =
      get().teams.find((t) => t.id === get().activeTeamId) ?? get().teams[0];
    const target = activeTeam?.agents.find((a) => a.id === agentId);
    if (!target || target.parent_id === null) {
      // Never delete the root supervisor agent
      return;
    }
    const fallbackParentId = target.parent_id;

    set((state) => ({
      teams: state.teams.map((team) => {
        const remaining = team.agents
          .filter((a) => a.id !== agentId)
          .map((a) =>
            a.parent_id === agentId
              ? {
                  ...a,
                  parent_id: fallbackParentId,
                  tier_level: Math.max(1, a.tier_level - 1),
                }
              : a
          );
        return {
          ...team,
          agents: remaining,
        };
      }),
      selectedAgentId: fallbackParentId ?? "agt_supervisor_utama",
    }));
    await deleteAgentRemote(agentId);
  },

  sendUserPrompt: async (promptText) => {
    const trimmed = promptText.trim();
    if (!trimmed) return;

    const activeWs = get().workspaces.find((w) => w.id === get().activeWorkspaceId);
    const folderPath = activeWs?.folder_path ?? "";

    const userMsg: ChatMessage = {
      id: `msg_${Date.now()}`,
      sender_role: "user",
      sender_name: "Anda",
      content: trimmed,
      timestamp_label: "Baru saja",
    };

    const activeTeam = get().teams.find((t) => t.id === get().activeTeamId) ?? get().teams[0];
    const supervisor = activeTeam?.agents.find((a) => a.parent_id === null) ?? activeTeam?.agents[0];
    const subAgents = activeTeam?.agents.filter((a) => a.id !== supervisor?.id) ?? [];

    const lower = trimmed.toLowerCase();
    const wantsDoc =
      /buat|bikin|generate|tulis|rekap|excel|xlsx|word|docx|surat|laporan|ppt|slide|presentasi|pdf/.test(
        lower
      );
    const wantsSearch = /cari|arsip|penelitian|riset|rag|fakta|dokumen/.test(lower);
    const wantsPy = /python|skrip|script|otomasi|csv|aplikasi/.test(lower);

    const targetSubAgent = subAgents.find((a) => {
      if (
        wantsDoc &&
        (a.tool_categories.includes("office_excel") ||
          a.tool_categories.includes("office_word") ||
          a.tool_categories.includes("office_ppt"))
      )
        return true;
      if (wantsSearch && a.tool_categories.includes("rag_search")) return true;
      if (
        wantsPy &&
        (a.tool_categories.includes("uv_python") || a.tool_categories.includes("os_automation"))
      )
        return true;
      return false;
    });

    const initStep: ExecutionStep = {
      id: `step_${Date.now()}_init`,
      agent_name: supervisor ? supervisor.name : "Manajer Eksekutif",
      agent_role: supervisor ? supervisor.role_title : "Koordinator Utama",
      provider: supervisor ? supervisor.provider : "gemini",
      model_id: supervisor ? supervisor.model_id : "gemini-3.8-flash",
      action_label: `Memahami tugas & menyiapkan langkah di folder ${activeWs?.name ?? "Ruang Kerja"}`,
      detail: targetSubAgent
        ? `Menyiapkan pembagian tugas ke ${targetSubAgent.name}...`
        : "Menyiapkan penyelesaian tugas langsung di ruang kerja Anda...",
      status: "running",
      tokens_used: 120,
      tokens_saved: 0,
    };

    set((state) => ({
      messages: [...state.messages, userMsg],
      isExecuting: true,
      activeAgentId: supervisor?.id ?? "agt_supervisor_utama",
      activeAgentStep: "Memahami tugas & menyiapkan langkah...",
      liveExecutionSteps: [initStep],
    }));

    let delegationTimer: ReturnType<typeof setTimeout> | null = null;
    if (targetSubAgent) {
      delegationTimer = setTimeout(() => {
        if (!get().isExecuting) return;
        const subStep: ExecutionStep = {
          id: `step_${Date.now()}_sub`,
          agent_name: targetSubAgent.name,
          agent_role: targetSubAgent.role_title,
          provider: targetSubAgent.provider,
          model_id: targetSubAgent.model_id,
          action_label: `Mengerjakan tugas di folder ${activeWs?.name ?? "Ruang Kerja"}`,
          detail: "Memproses dokumen dengan konteks terfokus agar hemat kuota.",
          status: "running",
          tokens_used: 420,
          tokens_saved: 4200,
        };
        set((state) => ({
          activeAgentId: targetSubAgent.id,
          activeAgentStep: `Mengerjakan dengan ${targetSubAgent.name}...`,
          liveExecutionSteps: [
            { ...state.liveExecutionSteps[0], status: "completed" },
            subStep,
          ],
        }));
      }, 850);
    }

    try {
      const priorMessages = get().messages.slice(0, -1);
      const recentHistory = priorMessages.slice(-8).map((m) => ({
        role: m.sender_role === "user" ? ("user" as const) : ("assistant" as const),
        sender_name: m.sender_name,
        content: m.content,
      }));

      const remoteRes = await executeTaskOnEngine({
        prompt: trimmed,
        team_id: get().activeTeamId,
        workspace_id: activeWs?.id,
        workspace_path: folderPath || undefined,
        session_id: get().activeWorkspaceId || "default_session",
        conversation_history: recentHistory,
      });

      if (remoteRes) {
        const taggedArtifacts = (remoteRes.artifacts || []).map((art) => ({
          ...art,
          artifact_category: art.artifact_category || ("final" as const),
        }));
        const replyMsg: ChatMessage = {
          id: `msg_${Date.now() + 1}`,
          sender_role: "supervisor",
          sender_name: remoteRes.supervisor_name,
          content: remoteRes.reply,
          timestamp_label: "Baru saja",
          execution_steps: remoteRes.execution_steps,
          artifacts: taggedArtifacts,
          suggested_followups: remoteRes.suggested_followups,
        };
        set((state) => {
          const nextMessages = [...state.messages, replyMsg];
          const nextArtifacts = [...taggedArtifacts, ...state.artifacts];
          void saveSystemSettingRemote("workspace_chat_state", {
            messages: nextMessages.slice(-40),
            artifacts: nextArtifacts.slice(0, 40),
          });
          return {
            messages: nextMessages,
            artifacts: nextArtifacts,
            totalTokensUsed: state.totalTokensUsed + remoteRes.tokens_used,
            totalTokensSaved: state.totalTokensSaved + remoteRes.tokens_saved,
            isArtifactDrawerOpen: taggedArtifacts.length > 0,
          };
        });
        return;
      }

      // Offline fallback
      const newArtifact: FileArtifact = {
        id: `art_${Date.now()}`,
        name: "Hasil_Pekerjaan_AKSA.xlsx",
        file_path: folderPath
          ? `${folderPath}/Hasil_Pekerjaan_AKSA.xlsx`
          : "Hasil_Pekerjaan_AKSA.xlsx",
        file_type: "xlsx",
        size_label: "36 KB",
        created_by_agent: targetSubAgent ? targetSubAgent.name : "Manajer Eksekutif",
        created_at_label: "Baru saja",
        summary: `Hasil akhir dibuat sesuai permintaan: "${trimmed.slice(0, 60)}"`,
        artifact_category: "final",
      };

      const replyMsg: ChatMessage = {
        id: `msg_${Date.now() + 1}`,
        sender_role: "supervisor",
        sender_name: "Manajer Eksekutif",
        content: `Permintaan Anda telah diselesaikan di dalam folder kerja **${activeWs?.name || "Ruang Kerja"}**. Hasil pekerjaan siap dibuka melalui kartu di bawah ini atau panel Hasil Pekerjaan di sebelah kanan.`,
        timestamp_label: "Baru saja",
        execution_steps: [
          { ...initStep, status: "completed" },
          ...(targetSubAgent
            ? [
                {
                  id: `step_${Date.now()}_sub_done`,
                  agent_name: targetSubAgent.name,
                  agent_role: targetSubAgent.role_title,
                  provider: targetSubAgent.provider,
                  model_id: targetSubAgent.model_id,
                  action_label: "Menyimpan file hasil pekerjaan di Folder Kerja",
                  detail: `File disimpan ke ${newArtifact.file_path}`,
                  status: "completed" as const,
                  tokens_used: 640,
                  tokens_saved: 2900,
                },
              ]
            : []),
        ],
        artifacts: wantsDoc ? [newArtifact] : [],
        suggested_followups: wantsDoc
          ? [
              {
                label: "Buat Laporan Ringkasan Word",
                prompt: "Buatkan dokumen ringkasan resmi (.docx) dari file hasil pekerjaan di atas.",
                requires_confirmation: false,
              },
              {
                label: "Ekspor ke Format PDF",
                prompt: "Konversikan dokumen hasil di atas ke format PDF siap cetak.",
                requires_confirmation: false,
              },
            ]
          : [
              {
                label: "Rangkum Poin Penting",
                prompt: "Buatkan ringkasan poin-poin utama dari penjelasan di atas.",
                requires_confirmation: false,
              },
            ],
      };

      set((state) => {
        const nextMessages = [...state.messages, replyMsg];
        const nextArtifacts = wantsDoc ? [newArtifact, ...state.artifacts] : state.artifacts;
        void saveSystemSettingRemote("workspace_chat_state", {
          messages: nextMessages.slice(-40),
          artifacts: nextArtifacts.slice(0, 40),
        });
        return {
          messages: nextMessages,
          artifacts: nextArtifacts,
          totalTokensUsed: state.totalTokensUsed + 760,
          totalTokensSaved: state.totalTokensSaved + 6500,
          isArtifactDrawerOpen: wantsDoc,
        };
      });
    } finally {
      if (delegationTimer) clearTimeout(delegationTimer);
      set({
        isExecuting: false,
        activeAgentId: null,
        activeAgentStep: null,
        liveExecutionSteps: [],
      });
    }
  },

  startNewChatSession: async () => {
    const currentMessages = get().messages;
    if (currentMessages.length > 0) {
      const archiveKey = `chat_session_${Date.now()}`;
      try {
        await saveSystemSettingRemote(archiveKey, {
          timestamp: new Date().toISOString(),
          messages: currentMessages,
          workspace_id: get().activeWorkspaceId,
        });
      } catch (err) {
        console.warn("Gagal mengarsipkan sesi percakapan ke basis data:", err);
      }
    }
    void saveSystemSettingRemote("workspace_chat_state", {
      messages: [],
      artifacts: get().artifacts.slice(0, 40),
    });
    set({
      messages: [],
      liveExecutionSteps: [],
      activeAgentStep: null,
      activeAgentId: null,
    });
    await get().loadSavedSessions();
  },

  syncWithBackendEngine: async () => {
    const isInitial = !get().isAppReady;
    if (isInitial) {
      set({
        initProgress: 25,
        initStepLabel: "Menghubungkan ke Mesin Layanan & Autentikasi...",
        initStage: { engine: "loading", database: "pending", workspace: "pending" },
      });
    }

    const minDelay = isInitial
      ? new Promise((resolve) => setTimeout(resolve, 650))
      : Promise.resolve();

    try {
      const [health, remoteSettings] = await Promise.all([
        fetchEngineHealth(),
        fetchSystemSettingsRemote(),
      ]);

      if (isInitial) {
        set({
          initProgress: 60,
          initStepLabel: "Menyiapkan basis data SQLite (aksa.db) & brankas kunci...",
          initStage: { engine: "done", database: "loading", workspace: "pending" },
        });
      }

      const [remoteTeams, remoteWorkspaces, remoteApprovals, remoteMcp, tokenAnalytics] =
        await Promise.all([
          fetchAgentTeams(),
          fetchWorkspaces(),
          fetchHITLApprovals(),
          fetchMCPServers(),
          fetchTokenAnalytics(),
        ]);

      if (isInitial) {
        set({
          initProgress: 90,
          initStepLabel: "Memuat struktur agen dan ruang kerja...",
          initStage: { engine: "done", database: "done", workspace: "loading" },
        });
      }

      // Auto-upgrade legacy cramped node positions if detected in remoteTeams
      const normalizedTeams =
        remoteTeams && remoteTeams.length > 0
          ? remoteTeams.map((team) => {
              const tier1 = team.agents.filter((a) => a.parent_id !== null);
              const isLegacyCramped =
                tier1.length >= 2 &&
                tier1.every((a) => a.position_y >= 240 && a.position_y <= 285);
              if (!isLegacyCramped) return team;
              const layoutMap = computeAutoHierarchyLayout(team.agents);
              return {
                ...team,
                agents: team.agents.map((agt) => {
                  const l = layoutMap[agt.id];
                  if (!l) return agt;
                  void saveAgentUpdate(agt.id, {
                    position_x: l.position_x,
                    position_y: l.position_y,
                    tier_level: l.tier_level,
                  });
                  return {
                    ...agt,
                    position_x: l.position_x,
                    position_y: l.position_y,
                    tier_level: l.tier_level,
                  };
                }),
              };
            })
          : null;

      await minDelay;

      set((state) => {
        const mergedWorkspaces =
          remoteWorkspaces && remoteWorkspaces.length > 0 ? remoteWorkspaces : state.workspaces;
        const dbWsId =
          typeof remoteSettings?.active_workspace_id === "string"
            ? remoteSettings.active_workspace_id
            : "";
        const savedWsId = dbWsId || getSavedStorage("aksa_active_workspace_id", "");
        const resolvedWsId =
          savedWsId && mergedWorkspaces.some((w) => w.id === savedWsId)
            ? savedWsId
            : mergedWorkspaces.some((w) => w.id === state.activeWorkspaceId)
            ? state.activeWorkspaceId
            : (mergedWorkspaces[0]?.id ?? state.activeWorkspaceId);

        const nextThemeMode: ThemeMode =
          remoteSettings?.theme_mode === "light" ||
          remoteSettings?.theme_mode === "dark" ||
          remoteSettings?.theme_mode === "system"
            ? remoteSettings.theme_mode
            : state.themeMode;
        const nextResolvedTheme = resolveEffectiveTheme(nextThemeMode, getSystemPrefersDark());
        const nextUiDensity: UIDensityMode =
          remoteSettings?.ui_density === "compact" || remoteSettings?.ui_density === "comfortable"
            ? remoteSettings.ui_density
            : state.uiDensity;
        const nextReducedMotion: boolean =
          typeof remoteSettings?.reduced_motion === "boolean"
            ? remoteSettings.reduced_motion
            : state.reducedMotion;

        if (typeof document !== "undefined") {
          document.documentElement.setAttribute("data-theme", nextResolvedTheme);
          document.documentElement.setAttribute("data-density", nextUiDensity);
          document.documentElement.setAttribute("data-reduce-motion", String(nextReducedMotion));
        }

        const persistedChat = remoteSettings?.workspace_chat_state;
        const restoredMessages =
          state.messages.length === 0 &&
          persistedChat &&
          Array.isArray(persistedChat.messages) &&
          persistedChat.messages.length > 0
            ? (persistedChat.messages as ChatMessage[])
            : state.messages;
        const restoredArtifacts =
          state.artifacts.length === 0 &&
          persistedChat &&
          Array.isArray(persistedChat.artifacts) &&
          persistedChat.artifacts.length > 0
            ? (persistedChat.artifacts as FileArtifact[])
            : state.artifacts;

        return {
          isAppReady: true,
          initProgress: 100,
          initStepLabel: "Aplikasi dan basis data siap digunakan.",
          initStage: { engine: "done", database: "done", workspace: "done" },
          engineHealth: health,
          themeMode: nextThemeMode,
          resolvedTheme: nextResolvedTheme,
          uiDensity: nextUiDensity,
          reducedMotion: nextReducedMotion,
          teams: normalizedTeams ?? state.teams,
          workspaces: mergedWorkspaces,
          activeWorkspaceId: resolvedWsId,
          messages: restoredMessages,
          artifacts: restoredArtifacts,
          pendingApprovals: remoteApprovals
            ? remoteApprovals.filter((a) => a.status === "pending")
            : state.pendingApprovals,
          mcpServers: remoteMcp && remoteMcp.length > 0 ? remoteMcp : state.mcpServers,
          totalTokensUsed:
            tokenAnalytics && tokenAnalytics.total_tokens_used !== undefined
              ? tokenAnalytics.total_tokens_used
              : state.totalTokensUsed,
          totalTokensSaved:
            tokenAnalytics && tokenAnalytics.total_tokens_saved !== undefined
              ? tokenAnalytics.total_tokens_saved
              : state.totalTokensSaved,
        };
      });
      void get().loadSavedSessions();
    } catch (err) {
      console.warn("[AKSA] Gagal sinkronisasi awal dengan mesin backend:", err);
      set({
        isAppReady: true,
        initProgress: 100,
        initStepLabel: "Masuk dalam mode mandiri.",
        initStage: { engine: "error", database: "done", workspace: "done" },
      });
    }
  },

  requestSampleApproval: async () => {
    const activeWs = get().workspaces.find((w) => w.id === get().activeWorkspaceId);
    const created = await createHITLApprovalRemote({
      tool_name: "run_custom_python_task",
      title_id: "Menjalankan Pemrosesan Data di Ruang Kerja",
      description_id: `Operator PC & Automasi Sistem meminta izin menjalankan pemrosesan data terisolasi di dalam folder "${activeWs?.name ?? "Ruang Kerja"}".`,
      risk_level: "high",
      target_path: activeWs?.folder_path ?? "",
    });
    const fallbackItem: HITLApprovalItem = created ?? {
      id: `hitl_${Date.now()}`,
      tool_name: "run_custom_python_task",
      risk_level: "high",
      title_id: "Menjalankan Pemrosesan Data di Ruang Kerja",
      description_id: `Operator PC & Automasi Sistem meminta izin menjalankan pemrosesan data terisolasi di dalam folder "${activeWs?.name ?? "Ruang Kerja"}".`,
      target_path: activeWs?.folder_path ?? "",
      agent_name: "Operator PC & Automasi Sistem",
      status: "pending",
      created_at: new Date().toISOString(),
    };
    set((state) => ({
      pendingApprovals: [fallbackItem, ...state.pendingApprovals],
    }));
  },

  resolveApproval: async (requestId, approved) => {
    await resolveHITLApprovalRemote(requestId, approved);
    set((state) => ({
      pendingApprovals: state.pendingApprovals.filter((item) => item.id !== requestId),
    }));
  },

  toggleMcpServer: async (serverId, enabled) => {
    await toggleMCPServerRemote(serverId, enabled);
    set((state) => ({
      mcpServers: state.mcpServers.map((s) =>
        s.id === serverId ? { ...s, enabled } : s
      ),
    }));
  },

  toggleEmergencyStop: async (active) => {
    await setEmergencyStopRemote(active);
    set({ emergencyStopActive: active });
  },
}));
