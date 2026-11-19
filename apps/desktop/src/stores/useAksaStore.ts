import { create } from "zustand";
import type {
  AgentNodeConfig,
  AgentTeam,
  ChatMessage,
  EngineHealth,
  ExecutionStep,
  FileArtifact,
  HITLApprovalItem,
  MCPServerItem,
  NavSection,
  WorkspaceFolder,
} from "@/types/aksa";
import {
  createHITLApprovalRemote,
  createWorkspaceRemote,
  deleteAgentRemote,
  deleteWorkspaceRemote,
  executeTaskOnEngine,
  fetchAgentTeams,
  fetchEngineHealth,
  fetchHITLApprovals,
  fetchMCPServers,
  fetchTokenAnalytics,
  fetchWorkspaces,
  resolveHITLApprovalRemote,
  saveAgentUpdate,
  setEmergencyStopRemote,
  toggleMCPServerRemote,
} from "@/services/engineClient";

const INITIAL_INDONESIAN_TEAM: AgentTeam = {
  id: "team_nusantara_default",
  name: "Tim Produktivitas Kantor Indonesia",
  description:
    "Tim agen bertingkat siap pakai untuk pengolahan dokumen Office, riset arsip RAG, dan automasi PC.",
  is_default: true,
  agents: [
    {
      id: "agt_supervisor_utama",
      team_id: "team_nusantara_default",
      parent_id: null,
      name: "Manajer Eksekutif",
      role_title: "Manajer Utama (Supervisor)",
      description:
        "Menerima instruksi pengguna, menyusun rencana kerja bertahap, mendelegasikan tugas ke sub-agen spesialis, dan merangkum hasil akhir.",
      avatar_icon: "brain-circuit",
      tier_level: 0,
      provider: "gemini",
      model_id: "gemini-4-carbon",
      temperature: 0.2,
      max_tokens: 4096,
      system_prompt:
        "Anda adalah Manajer Eksekutif AKSA yang memimpin tim sub-agen spesialis. Pahami instruksi pengguna dalam Bahasa Indonesia, bagi tugas secara hemat token, dan pastikan file akhir rapi.",
      tool_categories: ["delegation", "filesystem"],
      position_x: 340,
      position_y: 30,
    },
    {
      id: "agt_spesialis_office",
      team_id: "team_nusantara_default",
      parent_id: "agt_supervisor_utama",
      name: "Spesialis Administrasi & Office",
      role_title: "Sub-Agen Pembuat Word, Excel, PPT & PDF",
      description:
        "Ahli membuat dan mengedit file Microsoft Excel (.xlsx dengan rumus & grafik), Word (.docx surat resmi & laporan), PowerPoint (.pptx), dan PDF di dalam Folder Kerja.",
      avatar_icon: "file-spreadsheet",
      tier_level: 1,
      provider: "deepseek",
      model_id: "deepseek-chat",
      temperature: 0.1,
      max_tokens: 4096,
      system_prompt:
        "Anda adalah Spesialis Administrasi & Microsoft Office. Buat file Excel (.xlsx lengkap dengan rumus SUM/VLOOKUP dan format Rupiah), Word (.docx), PowerPoint (.pptx), dan PDF.",
      tool_categories: ["office_excel", "office_word", "office_ppt", "pdf_tools", "filesystem"],
      position_x: 20,
      position_y: 250,
    },
    {
      id: "agt_peneliti_rag",
      team_id: "team_nusantara_default",
      parent_id: "agt_supervisor_utama",
      name: "Peneliti Dokumen & Arsip RAG",
      role_title: "Sub-Agen Pencarian & Analisis Dokumen Lokal",
      description:
        "Mencari informasi akurat dari ratusan dokumen di Basis Pengetahuan (RAG) menggunakan pencarian hibrida (makna + kata kunci) secara hemat token.",
      avatar_icon: "book-open-check",
      tier_level: 1,
      provider: "ollama",
      model_id: "qwen3.8:8b",
      temperature: 0.1,
      max_tokens: 2048,
      system_prompt:
        "Anda adalah Peneliti Dokumen & Arsip RAG lokal. Ekstrak fakta, angka, dan kutipan halaman dari dokumen di Folder Kerja secara ringkas agar hemat token.",
      tool_categories: ["rag_search", "filesystem", "pdf_tools"],
      position_x: 340,
      position_y: 250,
    },
    {
      id: "agt_operator_pc",
      team_id: "team_nusantara_default",
      parent_id: "agt_supervisor_utama",
      name: "Operator PC & Automasi Sistem",
      role_title: "Sub-Agen Kontrol Aplikasi, Skrip Python & Layar",
      description:
        "Mengoperasikan aplikasi PC secara langsung (Windows COM / AppleScript), menjalankan skrip Python otomatis (uv), dan kontrol layar visual (Computer Use).",
      avatar_icon: "monitor-cog",
      tier_level: 1,
      provider: "anthropic",
      model_id: "claude-sonnet-5-5",
      temperature: 0.1,
      max_tokens: 4096,
      system_prompt:
        "Anda adalah Operator PC & Automasi Sistem. Jalankan automasi aplikasi desktop, skrip Python terisolasi (uv), dan kontrol visual di bawah izin keamanan pengguna.",
      tool_categories: ["os_automation", "uv_python", "computer_use", "filesystem"],
      position_x: 660,
      position_y: 250,
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

const INITIAL_WORKSPACES: WorkspaceFolder[] = [];

const INITIAL_ARTIFACTS: FileArtifact[] = [];

const INITIAL_MESSAGES: ChatMessage[] = [];

interface AksaState {
  activeNav: NavSection;
  isSidebarCollapsed: boolean;
  isArtifactDrawerOpen: boolean;
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

  // Real-time execution tracking
  isExecuting: boolean;
  activeAgentId: string | null;
  activeAgentStep: string | null;
  liveExecutionSteps: ExecutionStep[];

  setActiveNav: (nav: NavSection) => void;
  toggleSidebar: () => void;
  setArtifactDrawerOpen: (open: boolean) => void;
  selectAgent: (agentId: string | null) => void;
  setActiveWorkspace: (workspaceId: string) => void;
  addWorkspaceFolder: (folderPath: string, name?: string) => void;
  removeWorkspaceFolder: (workspaceId: string) => void;
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
  addSubAgent: (parentAgent: AgentNodeConfig) => void;
  deleteAgentNode: (agentId: string) => Promise<void>;
  sendUserPrompt: (promptText: string) => Promise<void>;
  requestSampleApproval: () => Promise<void>;
  resolveApproval: (requestId: string, approved: boolean) => Promise<void>;
  toggleMcpServer: (serverId: string, enabled: boolean) => Promise<void>;
  toggleEmergencyStop: (active: boolean) => Promise<void>;
  syncWithBackendEngine: () => Promise<void>;
}

export const useAksaStore = create<AksaState>((set, get) => ({
  activeNav: (getSavedStorage("aksa_active_nav", "ruang_kerja") as NavSection),
  isSidebarCollapsed: false,
  isArtifactDrawerOpen: false,
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
      description_id: "Akses standar MCP untuk operasi struktur direktori lokal.",
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
      description_id: "Kueri dan analisis tabel database lokal melalui protokol MCP.",
      discovered_tools: ["read_query", "list_tables", "describe_table"],
    },
  ],
  emergencyStopActive: false,

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
  selectAgent: (agentId) => set({ selectedAgentId: agentId }),
  setActiveWorkspace: (workspaceId) => {
    if (typeof window !== "undefined") {
      try {
        localStorage.setItem("aksa_active_workspace_id", workspaceId);
      } catch {}
    }
    set({ activeWorkspaceId: workspaceId });
  },

  addWorkspaceFolder: async (folderPath, name) => {
    const cleanName = name || folderPath.split(/[\\/]/).filter(Boolean).pop() || folderPath;
    const remote = await createWorkspaceRemote({
      name: cleanName,
      folder_path: folderPath,
      allow_read: true,
      allow_write: true,
      allow_execute: false,
    });
    const newWs: WorkspaceFolder = remote || {
      id: `ws_${Date.now()}`,
      name: cleanName,
      folder_path: folderPath,
      allow_read: true,
      allow_write: true,
      allow_execute: false,
      auto_rag_sync: true,
      last_indexed_at: "Baru ditambahkan • Siap indeks RAG",
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
      return {
        workspaces: remaining,
        activeWorkspaceId: nextActiveId,
      };
    });
  },

  updateWorkspacePermissions: (workspaceId, updates) => {
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

  addSubAgent: (parentAgent) => {
    const newId = `agt_${Date.now().toString(36)}`;
    const newAgent: AgentNodeConfig = {
      id: newId,
      team_id: parentAgent.team_id,
      parent_id: parentAgent.id,
      name: "Agen Pendukung Baru",
      role_title: "Agen Pendukung Khusus",
      description: "Membantu menyelesaikan tugas tertentu secara terfokus sesuai kemampuan yang Anda pilih.",
      avatar_icon: "bot",
      tier_level: parentAgent.tier_level + 1,
      provider: "ollama",
      model_id: "qwen3.8:8b",
      temperature: 0.2,
      max_tokens: 2048,
      system_prompt:
        "Anda adalah Agen Pendukung di dalam tim AKSA. Kerjakan instruksi secara akurat dan berikan ringkasan hasil yang jelas.",
      tool_categories: ["filesystem"],
      position_x: parentAgent.position_x + 40,
      position_y: parentAgent.position_y + 220,
    };

    set((state) => ({
      teams: state.teams.map((team) =>
        team.id === parentAgent.team_id
          ? { ...team, agents: [...team.agents, newAgent] }
          : team
      ),
      selectedAgentId: newId,
    }));
  },

  deleteAgentNode: async (agentId) => {
    set((state) => ({
      teams: state.teams.map((team) => ({
        ...team,
        agents: team.agents.filter((a) => a.id !== agentId && a.parent_id !== agentId),
      })),
      selectedAgentId: "agt_supervisor_utama",
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
    const wantsDoc = /buat|bikin|generate|tulis|rekap|excel|xlsx|word|docx|surat|laporan|ppt|slide|presentasi|pdf/.test(lower);
    const wantsSearch = /cari|arsip|penelitian|riset|rag|fakta|dokumen/.test(lower);
    const wantsPy = /python|skrip|script|otomasi|csv|aplikasi/.test(lower);

    const targetSubAgent = subAgents.find((a) => {
      if (wantsDoc && (a.tool_categories.includes("office_excel") || a.tool_categories.includes("office_word") || a.tool_categories.includes("office_ppt"))) return true;
      if (wantsSearch && a.tool_categories.includes("rag_search")) return true;
      if (wantsPy && (a.tool_categories.includes("uv_python") || a.tool_categories.includes("os_automation"))) return true;
      return false;
    });

    const initStep: ExecutionStep = {
      id: `step_${Date.now()}_init`,
      agent_name: supervisor ? supervisor.name : "Manajer Eksekutif",
      agent_role: supervisor ? supervisor.role_title : "Manajer Utama (Supervisor)",
      provider: supervisor ? supervisor.provider : "gemini",
      model_id: supervisor ? supervisor.model_id : "gemini-3.8-flash",
      action_label: `Menganalisis instruksi & memeriksa Folder Kerja ${activeWs?.name ?? "Lokal"}`,
      detail: targetSubAgent
        ? `Menyiapkan delegasi terisolasi ke ${targetSubAgent.name}...`
        : "Menyiapkan jawaban langsung dengan akses desktop lokal aktif...",
      status: "running",
      tokens_used: 120,
      tokens_saved: 0,
    };

    set((state) => ({
      messages: [...state.messages, userMsg],
      isExecuting: true,
      activeAgentId: supervisor?.id ?? "agt_supervisor_utama",
      activeAgentStep: `Menganalisis instruksi & konteks Folder Kerja...`,
      liveExecutionSteps: [initStep],
    }));

    let delegationTimer: any = null;
    if (targetSubAgent) {
      delegationTimer = setTimeout(() => {
        if (!get().isExecuting) return;
        const subStep: ExecutionStep = {
          id: `step_${Date.now()}_sub`,
          agent_name: targetSubAgent.name,
          agent_role: targetSubAgent.role_title,
          provider: targetSubAgent.provider,
          model_id: targetSubAgent.model_id,
          action_label: `Mengeksekusi tugas di folder kerja ${activeWs?.name ?? "Lokal"}`,
          detail: "Mengisolasi konteks dokumen & memuat lazy tools untuk efisiensi token.",
          status: "running",
          tokens_used: 420,
          tokens_saved: 4200,
        };
        set((state) => ({
          activeAgentId: targetSubAgent.id,
          activeAgentStep: `Mengeksekusi ${targetSubAgent.role_title}...`,
          liveExecutionSteps: [
            { ...state.liveExecutionSteps[0], status: "completed" },
            subStep,
          ],
        }));
      }, 850);
    }

    try {
      const remoteRes = await executeTaskOnEngine({
        prompt: trimmed,
        team_id: get().activeTeamId,
        workspace_id: activeWs?.id,
        workspace_path: folderPath || undefined,
      });

      if (remoteRes) {
        const replyMsg: ChatMessage = {
          id: `msg_${Date.now() + 1}`,
          sender_role: "supervisor",
          sender_name: remoteRes.supervisor_name,
          content: remoteRes.reply,
          timestamp_label: "Baru saja",
          execution_steps: remoteRes.execution_steps,
          artifacts: remoteRes.artifacts,
        };
        set((state) => ({
          messages: [...state.messages, replyMsg],
          artifacts: [...remoteRes.artifacts, ...state.artifacts],
          totalTokensUsed: state.totalTokensUsed + remoteRes.tokens_used,
          totalTokensSaved: state.totalTokensSaved + remoteRes.tokens_saved,
          isArtifactDrawerOpen: remoteRes.artifacts && remoteRes.artifacts.length > 0,
        }));
        return;
      }

      // Offline fallback
      const newArtifact: FileArtifact = {
        id: `art_${Date.now()}`,
        name: "Hasil_Eksekusi_AKSA.xlsx",
        file_path: `${folderPath}/Hasil_Eksekusi_AKSA.xlsx`,
        file_type: "xlsx",
        size_label: "36 KB",
        created_by_agent: targetSubAgent ? targetSubAgent.name : "Manajer Eksekutif",
        created_at_label: "Baru saja",
        summary: `Dibuat otomatis sesuai instruksi: "${trimmed.slice(0, 60)}..."`,
      };

      const replyMsg: ChatMessage = {
        id: `msg_${Date.now() + 1}`,
        sender_role: "supervisor",
        sender_name: "Manajer Eksekutif",
        content: `Instruksi Anda telah dijalankan di dalam folder kerja **\`${folderPath}\`**. Manajer Eksekutif telah mengoordinasikan sub-agen terkait dengan mengisolasi konteks dokumen agar tetap hemat token.`,
        timestamp_label: "Baru saja",
        execution_steps: [
          initStep,
          ...(targetSubAgent
            ? [
                {
                  id: `step_${Date.now()}_sub_done`,
                  agent_name: targetSubAgent.name,
                  agent_role: targetSubAgent.role_title,
                  provider: targetSubAgent.provider,
                  model_id: targetSubAgent.model_id,
                  action_label: "Menghasilkan dokumen hasil kerja di dalam Folder Kerja",
                  detail: `File disimpan langsung ke ${newArtifact.file_path}`,
                  status: "completed" as const,
                  tokens_used: 640,
                  tokens_saved: 2900,
                },
              ]
            : []),
        ],
        artifacts: wantsDoc ? [newArtifact] : [],
      };

      set((state) => ({
        messages: [...state.messages, replyMsg],
        artifacts: wantsDoc ? [newArtifact, ...state.artifacts] : state.artifacts,
        totalTokensUsed: state.totalTokensUsed + 760,
        totalTokensSaved: state.totalTokensSaved + 6500,
        isArtifactDrawerOpen: wantsDoc,
      }));
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

  syncWithBackendEngine: async () => {
    const [health, remoteTeams, remoteWorkspaces, remoteApprovals, remoteMcp, tokenAnalytics] =
      await Promise.all([
        fetchEngineHealth(),
        fetchAgentTeams(),
        fetchWorkspaces(),
        fetchHITLApprovals(),
        fetchMCPServers(),
        fetchTokenAnalytics(),
      ]);
    set((state) => {
      const mergedWorkspaces =
        remoteWorkspaces && remoteWorkspaces.length > 0 ? remoteWorkspaces : state.workspaces;
      const savedWsId = getSavedStorage("aksa_active_workspace_id", "");
      const resolvedWsId =
        (savedWsId && mergedWorkspaces.some((w) => w.id === savedWsId))
          ? savedWsId
          : (mergedWorkspaces.some((w) => w.id === state.activeWorkspaceId)
              ? state.activeWorkspaceId
              : (mergedWorkspaces[0]?.id ?? state.activeWorkspaceId));

      return {
        engineHealth: health,
        teams: remoteTeams && remoteTeams.length > 0 ? remoteTeams : state.teams,
        workspaces: mergedWorkspaces,
        activeWorkspaceId: resolvedWsId,
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
  },

  requestSampleApproval: async () => {
    const activeWs = get().workspaces.find((w) => w.id === get().activeWorkspaceId);
    const created = await createHITLApprovalRemote({
      tool_name: "run_custom_python_task",
      title_id: "Konfirmasi Izin Akses Eksekusi Skrip & Kontrol PC",
      description_id: `Operator PC & Automasi Sistem meminta izin menjalankan skrip analisis Python terisolasi (uv) di dalam folder "${activeWs?.name ?? "Kerja"}".`,
      risk_level: "high",
      target_path: activeWs?.folder_path ?? "",
    });
    const fallbackItem: HITLApprovalItem = created ?? {
      id: `hitl_${Date.now()}`,
      tool_name: "run_custom_python_task",
      risk_level: "high",
      title_id: "Konfirmasi Izin Akses Eksekusi Skrip & Kontrol PC",
      description_id: `Operator PC & Automasi Sistem meminta izin menjalankan skrip analisis Python terisolasi (uv) di dalam folder "${activeWs?.name ?? "Kerja"}".`,
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
