import React, { useMemo, useState, useEffect } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Handle,
  Position,
  type Node,
  type Edge,
  type NodeProps,
  type Connection,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  Plus,
  Cpu,
  Cloud,
  Sparkles,
  Check,
  Network,
  SlidersHorizontal,
  ListTree,
  Trash2,
  Edit3,
  ShieldAlert,
  ShieldCheck,
  Laptop,
  FileSpreadsheet,
  Globe,
  Code2,
  MessageSquare,
  Wrench,
  Wand2,
  Save,
  Play,
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  GitBranch,
  LayoutTemplate,
  Info,
} from "lucide-react";
import { toast } from "sonner";
import { useAksaStore } from "@/stores/useAksaStore";
import {
  cn,
  getHumanModelInfo,
  getProviderBadgeStyle,
  MODEL_METADATA_LIST,
  TOOL_CATEGORY_LABELS,
  TOOL_CATEGORY_DESCRIPTIONS,
  wouldCreateAgentCycle,
  formatProviderTokenStatus,
} from "@/lib/utils";
import { ProviderIcon, ToolCategoryIcon } from "@/components/ui/DynamicIcon";
import { ConfirmDialog, EmptyStateCard, StatusBadge } from "@/components/ui/UXPrimitives";
import type {
  AgentNodeConfig,
  ModelProvider,
  DesktopApp,
  SkillItem,
  ProviderStatusDetail,
} from "@/types/aksa";
import {
  fetchDesktopAppsRemote,
  fetchDiscoveredModelsRemote,
  fetchProviderDetails,
  fetchSkillsRemote,
  testModelConnectionRemote,
} from "@/services/engineClient";

interface JobTemplate {
  id: string;
  label: string;
  roleTitle: string;
  description: string;
  systemPrompt: string;
  capabilities: string[];
  recommendedProvider: ModelProvider;
  recommendedModel: string;
  recommendedLabel: string;
}

const JOB_TEMPLATES: JobTemplate[] = [
  {
    id: "asisten_dokumen",
    label: "Asisten dokumen",
    roleTitle: "Agen Pendukung Dokumen Word, Excel & PDF",
    description:
      "Membantu menyusun surat, merapikan laporan Word, membuat tabel Excel, serta membaca atau menyimpan PDF.",
    systemPrompt:
      "Anda adalah Asisten Dokumen AKSA. Susun laporan Word, tabel Excel, presentasi, dan PDF dengan rapi dalam Bahasa Indonesia.",
    capabilities: ["filesystem", "office_word", "office_excel", "pdf_tools"],
    recommendedProvider: "deepseek",
    recommendedModel: "deepseek-chat",
    recommendedLabel: "DeepSeek Chat (Optimal untuk Dokumen & Office)",
  },
  {
    id: "analis_data",
    label: "Analis data",
    roleTitle: "Agen Pendukung Olah Data & Tabel",
    description:
      "Mengolah angka, membuat rumus rekapitulasi Excel, dan menyusun kesimpulan dari data tabel atau CSV.",
    systemPrompt:
      "Anda adalah Analis Data AKSA. Periksa ketelitian angka, rumus Excel, dan sajikan temuan data secara ringkas.",
    capabilities: ["filesystem", "office_excel", "uv_python"],
    recommendedProvider: "deepseek",
    recommendedModel: "deepseek-v4-pro",
    recommendedLabel: "DeepSeek V4 Pro (Rekomendasi Analisis Angka & Tabel)",
  },
  {
    id: "riset_informasi",
    label: "Riset informasi",
    roleTitle: "Agen Pendukung Pencarian & Ringkasan Dokumen",
    description:
      "Mencari informasi penting dari koleksi dokumen di Pengetahuan AKSA dan merangkumnya secara padat.",
    systemPrompt:
      "Anda adalah Agen Riset Informasi AKSA. Cari fakta dan kutipan yang relevan dari dokumen pengguna secara akurat.",
    capabilities: ["rag_search", "filesystem", "pdf_tools"],
    recommendedProvider: "ollama",
    recommendedModel: "qwen3.8:8b",
    recommendedLabel: "Qwen 3.8 8B Lokal (Hemat Kuota & Privasi Lokal)",
  },
  {
    id: "asisten_administrasi",
    label: "Asisten administrasi",
    roleTitle: "Agen Pendukung Administrasi & Presentasi",
    description:
      "Membantu pekerjaan administrasi harian, merapikan arsip folder, dan menyiapkan salindia presentasi.",
    systemPrompt:
      "Anda adalah Asisten Administrasi AKSA. Bantu pekerjaan surat-menyurat, arsip file, dan presentasi kantor secara rapi.",
    capabilities: ["filesystem", "office_word", "office_ppt", "office_excel"],
    recommendedProvider: "gemini",
    recommendedModel: "gemini-3.8-flash",
    recommendedLabel: "Gemini 3.8 Flash (Cepat & Responsif)",
  },
  {
    id: "asisten_pemrograman",
    label: "Asisten pemrograman",
    roleTitle: "Agen Pendukung Kode & Skrip Otomatis",
    description:
      "Menulis dan memeriksa skrip pemrosesan otomatis di dalam Area Kerja Terlindungi.",
    systemPrompt:
      "Anda adalah Asisten Pemrograman AKSA. Tulis kode yang aman, bersih, dan teruji di dalam area kerja yang diizinkan.",
    capabilities: ["filesystem", "uv_python"],
    recommendedProvider: "anthropic",
    recommendedModel: "claude-sonnet-5-5",
    recommendedLabel: "Claude Sonnet 5.5 (Rekomendasi Pemrograman)",
  },
  {
    id: "agen_khusus",
    label: "Agen khusus",
    roleTitle: "Agen Pendukung Kustom",
    description:
      "Sesuaikan sendiri tugas, instruksi, dan kemampuan agen sesuai kebutuhan spesifik pekerjaan Anda.",
    systemPrompt:
      "Anda adalah Agen Pendukung Khusus di dalam tim AKSA. Selesaikan tugas sesuai instruksi pengguna dengan teliti.",
    capabilities: ["filesystem"],
    recommendedProvider: "gemini",
    recommendedModel: "gemini-4-argon",
    recommendedLabel: "Gemini 4 Argon (Serbaguna untuk Tugas Khusus)",
  },
];

const PROVIDER_LIST: { id: ModelProvider; label: string; isLocal: boolean }[] = [
  { id: "gemini", label: "Google Gemini", isLocal: false },
  { id: "anthropic", label: "Anthropic Claude", isLocal: false },
  { id: "deepseek", label: "DeepSeek", isLocal: false },
  { id: "openai", label: "OpenAI", isLocal: false },
  { id: "groq", label: "Groq Cloud", isLocal: false },
  { id: "openrouter", label: "OpenRouter", isLocal: false },
  { id: "ollama", label: "Ollama (AI Lokal)", isLocal: true },
  { id: "lmstudio", label: "LM Studio (AI Lokal)", isLocal: true },
];

type AgentRuntimeStatus = "Siap" | "Bekerja" | "Menunggu persetujuan";

type AgentFlowNodeData = {
  agent: AgentNodeConfig;
  parentName: string | null;
  subAgentCount: number;
  runtimeStatus: AgentRuntimeStatus;
  isSelected: boolean;
  isActive: boolean;
  activeStepLabel?: string | null;
  onSelect: (id: string) => void;
  onAddChild: (agent: AgentNodeConfig) => void;
};

const AgentCustomFlowNode: React.FC<NodeProps<Node<AgentFlowNodeData>>> = ({ data }) => {
  const {
    agent,
    parentName,
    subAgentCount,
    runtimeStatus,
    isSelected,
    isActive,
    activeStepLabel,
    onSelect,
    onAddChild,
  } = data;
  const badge = getProviderBadgeStyle(agent.provider);
  const modelMeta = getHumanModelInfo(agent.provider, agent.model_id);
  const isRoot = agent.parent_id === null;

  const statusTone =
    runtimeStatus === "Bekerja"
      ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/35"
      : runtimeStatus === "Menunggu persetujuan"
      ? "bg-amber-500/15 text-amber-300 border-amber-500/35"
      : "bg-white/[0.06] text-zinc-300 border-white/[0.08]";

  return (
    <div
      onClick={() => onSelect(agent.id)}
      className={cn(
        "w-[300px] rounded-2xl p-4 cursor-pointer transition-all border text-left space-y-2.5 shadow-xl select-none relative",
        isActive
          ? "bg-[#212921] border-emerald-500 ring-2 ring-emerald-500/40"
          : isSelected
          ? "bg-[#262624] border-[#D97757] ring-2 ring-[#D97757]/35"
          : "bg-[#21211F] border-white/[0.12] hover:border-white/[0.24]"
      )}
    >
      {!isRoot && (
        <Handle
          type="target"
          position={Position.Top}
          className="!w-3 !h-3 !bg-[#D97757] !border-2 !border-[#191918]"
        />
      )}

      {/* Top Row: Role Badge & Runtime Status (Section 3 Informasi Node) */}
      <div className="flex items-center justify-between gap-2">
        <span
          className={cn(
            "rounded-md px-2 py-0.5 text-[11px] font-semibold border",
            isRoot
              ? "bg-[#D97757]/15 text-[#F09373] border-[#D97757]/35"
              : "bg-white/[0.06] text-zinc-200 border-white/[0.08]"
          )}
        >
          {isRoot ? "Asisten Utama (Root)" : `Membantu ${parentName || "Tim"}`}
        </span>

        <span
          className={cn(
            "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-medium",
            statusTone
          )}
        >
          <span
            className={cn(
              "h-1.5 w-1.5 rounded-full",
              runtimeStatus === "Bekerja"
                ? "bg-emerald-400 animate-ping"
                : runtimeStatus === "Menunggu persetujuan"
                ? "bg-amber-400"
                : "bg-emerald-400"
            )}
          />
          <span>{runtimeStatus}</span>
        </span>
      </div>

      {/* Agent Name & Concise Responsibility */}
      <div>
        <div className="text-[14.5px] font-semibold text-zinc-100 truncate">{agent.name}</div>
        <p className="text-xs text-zinc-300 truncate mt-0.5">{agent.role_title}</p>
      </div>

      {isActive && activeStepLabel && (
        <div className="rounded-lg bg-emerald-500/15 border border-emerald-500/30 px-2.5 py-1 text-xs text-emerald-300 truncate">
          {activeStepLabel}
        </div>
      )}

      {/* Human-Friendly Active Model Pill (Section 3 & 4) */}
      <div className="flex items-center justify-between rounded-xl bg-black/30 border border-white/[0.06] px-2.5 py-1.5">
        <div className="flex items-center gap-1.5 min-w-0">
          {badge.isLocal ? (
            <Cpu size={13} className="text-emerald-400 shrink-0" />
          ) : (
            <Cloud size={13} className="text-[#D97757] shrink-0" />
          )}
          <span className="text-xs font-medium text-zinc-100 truncate">
            {modelMeta.friendlyName}
          </span>
        </div>
        <span className="text-[11px] text-zinc-400 shrink-0 ml-1">
          {agent.model_selection_mode === "manual" ? "Manual" : "Otomatis"}
        </span>
      </div>

      {/* Footer: Capability Count Summary & Add Sub-Agent Action */}
      <div className="flex items-center justify-between pt-1 text-xs text-zinc-300">
        <span>
          {agent.tool_categories.length} kemampuan aktif
          {subAgentCount > 0 ? ` • ${subAgentCount} sub-agen` : ""}
        </span>

        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onAddChild(agent);
          }}
          title={`Tambah sub-agen di bawah ${agent.name}`}
          className="inline-flex items-center gap-1 rounded-lg bg-white/[0.06] hover:bg-[#D97757]/20 hover:text-[#F09373] border border-white/[0.08] px-2 py-1 text-[11px] font-medium text-zinc-200 transition-colors"
        >
          <Plus size={11} />
          <span>Sub-agen</span>
        </button>
      </div>

      <Handle
        type="source"
        position={Position.Bottom}
        className="!w-3 !h-3 !bg-emerald-400 !border-2 !border-[#191918]"
      />
    </div>
  );
};

const nodeTypes = {
  aksaAgent: AgentCustomFlowNode,
};

export const AgentHierarchyView: React.FC = () => {
  const {
    teams,
    activeTeamId,
    selectedAgentId,
    selectAgent,
    updateAgentConfig,
    addSubAgent,
    reparentAgent,
    autoLayoutAgents,
    deleteAgentNode,
    engineHealth,
    isExecuting,
    activeAgentId,
    activeAgentStep,
    pendingApprovals,
    reducedMotion,
    setActiveNav,
  } = useAksaStore();

  // Diagram vs Accessible List view (Section 3: Diagram is primary default, Daftar is accessible alternative)
  const [viewMode, setViewMode] = useState<"diagram" | "list">("diagram");
  // Simple Mode is default for the configuration panel; Advanced Mode reveals technical parameters
  const [experienceMode, setExperienceMode] = useState<"sederhana" | "lanjutan">("sederhana");

  const [selectedTemplateId, setSelectedTemplateId] = useState<string>("asisten_dokumen");
  const [connectedApps, setConnectedApps] = useState<DesktopApp[]>([]);
  const [installedSkills, setInstalledSkills] = useState<SkillItem[]>([]);
  const [providerStatuses, setProviderStatuses] = useState<Record<string, ProviderStatusDetail>>(
    {}
  );
  const [discoveredModelsByProvider, setDiscoveredModelsByProvider] = useState<
    Record<string, string[]>
  >({});
  const [toolsTab, setToolsTab] = useState<"core" | "apps" | "skills">("core");

  // Modals & Confirmations
  const [agentPendingDelete, setAgentPendingDelete] = useState<AgentNodeConfig | null>(null);
  const [pendingReparent, setPendingReparent] = useState<{
    agentId: string;
    newParentId: string;
  } | null>(null);
  const [pendingAutoOverwrite, setPendingAutoOverwrite] = useState(false);
  const [addAgentModalParent, setAddAgentModalParent] = useState<AgentNodeConfig | null>(null);
  const [newAgentTemplateId, setNewAgentTemplateId] = useState<string>("asisten_dokumen");
  const [newAgentName, setNewAgentName] = useState<string>("");

  // Custom technical model ID state (for advanced manual override)
  const [showCustomModelInput, setShowCustomModelInput] = useState(false);
  const [customModelIdInput, setCustomModelIdInput] = useState("");
  const [modelTestStatus, setModelTestStatus] = useState<{
    loading: boolean;
    ok?: boolean;
    message?: string;
  } | null>(null);
  const [showAdvancedAccordion, setShowAdvancedAccordion] = useState(false);

  useEffect(() => {
    void (async () => {
      try {
        const [apps, skillsData, provDetails, discModels] = await Promise.all([
          fetchDesktopAppsRemote(),
          fetchSkillsRemote(),
          fetchProviderDetails(),
          fetchDiscoveredModelsRemote(),
        ]);
        if (apps) {
          setConnectedApps(apps.filter((a) => a.is_connected));
        }
        if (skillsData?.installed_skills) {
          setInstalledSkills(skillsData.installed_skills);
        }
        if (provDetails?.providers) {
          const map: Record<string, ProviderStatusDetail> = {};
          for (const p of provDetails.providers) {
            map[p.id] = p;
          }
          setProviderStatuses(map);
        }
        if (discModels?.providers && typeof discModels.providers === "object") {
          const dmap: Record<string, string[]> = {};
          for (const [pid, mlist] of Object.entries(discModels.providers)) {
            if (Array.isArray(mlist)) {
              dmap[pid] = mlist
                .map((m: any) => (typeof m === "string" ? m : m?.id || m?.model_id))
                .filter(Boolean);
            }
          }
          setDiscoveredModelsByProvider(dmap);
        }
      } catch {}
    })();
  }, []);

  const activeTeam = teams.find((t) => t.id === activeTeamId) ?? teams[0];
  const agents = activeTeam?.agents ?? [];
  const selectedAgent = agents.find((a) => a.id === selectedAgentId) ?? agents[0] ?? null;

  useEffect(() => {
    setModelTestStatus(null);
    setShowCustomModelInput(false);
  }, [selectedAgent?.id]);

  // Available models for the currently selected provider (from discovered + provider status + catalog)
  const availableModelsForProvider = useMemo(() => {
    if (!selectedAgent) return [];
    const prov = selectedAgent.provider;
    const ids = new Set<string>();

    if (prov === "ollama" && engineHealth.ollama_online) {
      for (const m of engineHealth.ollama_models) ids.add(m);
    }
    const provStatus = providerStatuses[prov];
    if (provStatus?.installed_models) {
      for (const m of provStatus.installed_models) ids.add(m);
    }
    const disc = discoveredModelsByProvider[prov];
    if (disc) {
      for (const m of disc) ids.add(m);
    }
    for (const item of MODEL_METADATA_LIST) {
      if (item.provider === prov) ids.add(item.model_id);
    }
    // Always include the agent's current model_id so it is never silently lost
    if (selectedAgent.model_id) {
      ids.add(selectedAgent.model_id);
    }

    return Array.from(ids).map((mid) => getHumanModelInfo(prov, mid));
  }, [
    selectedAgent,
    engineHealth.ollama_online,
    engineHealth.ollama_models,
    providerStatuses,
    discoveredModelsByProvider,
  ]);

  const getAgentRuntimeStatus = (agentId: string): AgentRuntimeStatus => {
    if (pendingApprovals.length > 0 && activeAgentId === agentId) {
      return "Menunggu persetujuan";
    }
    if (isExecuting && activeAgentId === agentId) {
      return "Bekerja";
    }
    return "Siap";
  };

  const handleOpenAddAgentModal = (parent?: AgentNodeConfig) => {
    const supervisor = agents.find((a) => a.parent_id === null) ?? agents[0];
    const targetParent = parent ?? selectedAgent ?? supervisor ?? null;
    setAddAgentModalParent(targetParent);
    setNewAgentTemplateId("asisten_dokumen");
    setNewAgentName("");
  };

  const handleConfirmCreateAgent = async () => {
    if (!addAgentModalParent) return;
    const tpl =
      JOB_TEMPLATES.find((t) => t.id === newAgentTemplateId) ?? JOB_TEMPLATES[0];
    const cleanName = newAgentName.trim() || tpl.label;
    await addSubAgent(addAgentModalParent, {
      name: cleanName,
      role_title: tpl.roleTitle,
      description: tpl.description,
      system_prompt: tpl.systemPrompt,
      tool_categories: tpl.capabilities,
      provider: tpl.recommendedProvider,
      model_id: tpl.recommendedModel,
      model_selection_mode: "auto",
    });
    setAddAgentModalParent(null);
    toast.success(`Agen "${cleanName}" berhasil ditambahkan di bawah ${addAgentModalParent.name}.`);
  };

  // React Flow Nodes derived directly from store agents
  const flowNodes: Node<AgentFlowNodeData>[] = useMemo(() => {
    const byId = new Map(agents.map((a) => [a.id, a]));
    return agents.map((agent) => {
      const parent = agent.parent_id ? byId.get(agent.parent_id) : null;
      const subCount = agents.filter((a) => a.parent_id === agent.id).length;
      return {
        id: agent.id,
        type: "aksaAgent",
        position: { x: agent.position_x, y: agent.position_y },
        data: {
          agent,
          parentName: parent ? parent.name : null,
          subAgentCount: subCount,
          runtimeStatus: getAgentRuntimeStatus(agent.id),
          isSelected: selectedAgent?.id === agent.id,
          isActive: Boolean(isExecuting && activeAgentId === agent.id),
          activeStepLabel: isExecuting && activeAgentId === agent.id ? activeAgentStep : null,
          onSelect: selectAgent,
          onAddChild: (parentAgt) => handleOpenAddAgentModal(parentAgt),
        },
      };
    });
  }, [
    agents,
    selectedAgent?.id,
    isExecuting,
    activeAgentId,
    activeAgentStep,
    pendingApprovals.length,
    selectAgent,
  ]);

  // React Flow Edges — ONLY animated when a task is actively running (Section 3 & 13.A)
  const flowEdges: Edge[] = useMemo(
    () =>
      agents
        .filter((a) => a.parent_id !== null)
        .map((a) => {
          const isDelegationActive = Boolean(
            isExecuting && (activeAgentId === a.id || activeAgentId === a.parent_id)
          );
          return {
            id: `edge_${a.parent_id}_${a.id}`,
            source: a.parent_id as string,
            target: a.id,
            animated: isDelegationActive && !reducedMotion,
            style: isDelegationActive
              ? { stroke: "#10B981", strokeWidth: 3 }
              : { stroke: "#D97757", strokeWidth: 2, opacity: 0.75 },
          };
        }),
    [agents, isExecuting, activeAgentId, reducedMotion]
  );

  const handleRequestReparent = (agentId: string, candidateParentId: string) => {
    const current = agents.find((a) => a.id === agentId);
    if (!current || current.parent_id === candidateParentId) return;
    if (current.parent_id === null) {
      toast.error("Asisten Utama (root) memimpin tim dan tidak dapat dijadikan sub-agen.");
      return;
    }
    if (wouldCreateAgentCycle(agents, agentId, candidateParentId)) {
      toast.error(
        "Relasi melingkar (circular dependency) ditolak: Agen induk tidak boleh berada di bawah sub-agen ini."
      );
      return;
    }
    setPendingReparent({ agentId, newParentId: candidateParentId });
  };

  const handleConnectNodes = (connection: Connection) => {
    if (!connection.source || !connection.target) return;
    // In our top-down hierarchy: source is parent, target is child
    handleRequestReparent(connection.target, connection.source);
  };

  const toggleToolCategory = (categoryKey: string) => {
    if (!selectedAgent) return;
    const exists = selectedAgent.tool_categories.includes(categoryKey);
    const updated = exists
      ? selectedAgent.tool_categories.filter((c) => c !== categoryKey)
      : [...selectedAgent.tool_categories, categoryKey];
    void updateAgentConfig(selectedAgent.id, { tool_categories: updated });
  };

  const isAppAllowed = (appId: string) => {
    if (!selectedAgent) return false;
    return (
      selectedAgent.tool_categories.includes(`app:${appId}`) ||
      selectedAgent.tool_categories.includes(appId)
    );
  };

  const toggleAppPermission = (appId: string) => {
    if (!selectedAgent) return;
    const key = `app:${appId}`;
    const allowed = isAppAllowed(appId);
    const updated = allowed
      ? selectedAgent.tool_categories.filter((c) => c !== key && c !== appId)
      : [...selectedAgent.tool_categories, key];
    void updateAgentConfig(selectedAgent.id, { tool_categories: updated });
  };

  const isSkillAssigned = (skillId: string) => {
    if (!selectedAgent) return false;
    return (
      selectedAgent.tool_categories.includes(`skill:${skillId}`) ||
      selectedAgent.tool_categories.includes(skillId)
    );
  };

  const toggleSkillAssignment = (skillId: string) => {
    if (!selectedAgent) return;
    const key = `skill:${skillId}`;
    const assigned = isSkillAssigned(skillId);
    const updated = assigned
      ? selectedAgent.tool_categories.filter((c) => c !== key && c !== skillId)
      : [...selectedAgent.tool_categories, key];
    void updateAgentConfig(selectedAgent.id, { tool_categories: updated });
  };

  const getAppCategoryIcon = (category?: string) => {
    switch (category) {
      case "Otomasi Dokumen Office":
        return <FileSpreadsheet className="w-3.5 h-3.5 text-[#D97757]" />;
      case "Navigasi & Analisis Web":
        return <Globe className="w-3.5 h-3.5 text-[#38BDF8]" />;
      case "Penyunting Kode & Teks":
        return <Code2 className="w-3.5 h-3.5 text-[#A78BFA]" />;
      case "Komunikasi & Produktivitas":
        return <MessageSquare className="w-3.5 h-3.5 text-[#34D399]" />;
      case "Alat Sistem & Utilitas":
        return <Wrench className="w-3.5 h-3.5 text-[#FBBF24]" />;
      default:
        return <Laptop className="w-3.5 h-3.5 text-[#9C9A92]" />;
    }
  };

  const handleApplyJobTemplate = (tpl: JobTemplate) => {
    setSelectedTemplateId(tpl.id);
    if (!selectedAgent) return;
    const isManualModel = selectedAgent.model_selection_mode === "manual";
    // Section 4: Automatic recommendation must NEVER overwrite a manual model choice without user consent
    void updateAgentConfig(selectedAgent.id, {
      role_title: tpl.roleTitle,
      description: tpl.description,
      system_prompt: tpl.systemPrompt,
      tool_categories: tpl.capabilities,
      ...(isManualModel
        ? {}
        : {
            provider: tpl.recommendedProvider,
            model_id: tpl.recommendedModel,
            model_selection_mode: "auto",
          }),
    });
    toast.success(
      isManualModel
        ? `Template "${tpl.label}" diterapkan (pilihan model manual Anda tetap dipertahankan).`
        : `Template "${tpl.label}" diterapkan pada ${selectedAgent.name}.`
    );
  };

  const applyRecommendedModelNow = () => {
    if (!selectedAgent) return;
    const activeTpl =
      JOB_TEMPLATES.find((t) => t.id === selectedTemplateId) ?? JOB_TEMPLATES[0];
    const provider: ModelProvider = engineHealth.ollama_online
      ? "ollama"
      : activeTpl.recommendedProvider;
    const model_id =
      engineHealth.ollama_online && engineHealth.ollama_models.length > 0
        ? engineHealth.ollama_models[0]
        : activeTpl.recommendedModel;
    void updateAgentConfig(selectedAgent.id, {
      provider,
      model_id,
      model_selection_mode: "auto",
    });
    setPendingAutoOverwrite(false);
    const meta = getHumanModelInfo(provider, model_id);
    toast.success(`Mode Otomatis aktif: menggunakan ${meta.friendlyName}.`);
  };

  const handleSelectModelMode = (mode: "auto" | "manual") => {
    if (!selectedAgent) return;
    if (mode === "manual") {
      void updateAgentConfig(selectedAgent.id, { model_selection_mode: "manual" });
      return;
    }
    // Switching from manual to auto: confirm before overwriting user's manual selection (Section 4)
    if (selectedAgent.model_selection_mode === "manual") {
      setPendingAutoOverwrite(true);
    } else {
      applyRecommendedModelNow();
    }
  };

  const handleManualProviderChange = (newProvider: ModelProvider) => {
    if (!selectedAgent) return;
    const firstModelForProvider =
      (newProvider === "ollama" && engineHealth.ollama_models[0]) ||
      providerStatuses[newProvider]?.installed_models?.[0] ||
      MODEL_METADATA_LIST.find((m) => m.provider === newProvider)?.model_id ||
      selectedAgent.model_id;

    void updateAgentConfig(selectedAgent.id, {
      provider: newProvider,
      model_id: firstModelForProvider,
      model_selection_mode: "manual",
    });
    setModelTestStatus(null);
  };

  const handleManualModelChange = (newModelId: string) => {
    if (!selectedAgent) return;
    if (newModelId === "__custom__") {
      setShowCustomModelInput(true);
      setCustomModelIdInput(selectedAgent.model_id);
      return;
    }
    setShowCustomModelInput(false);
    void updateAgentConfig(selectedAgent.id, {
      model_id: newModelId,
      model_selection_mode: "manual",
    });
    setModelTestStatus(null);
  };

  const handleApplyCustomModelId = () => {
    if (!selectedAgent || !customModelIdInput.trim()) return;
    void updateAgentConfig(selectedAgent.id, {
      model_id: customModelIdInput.trim(),
      model_selection_mode: "manual",
    });
    setShowCustomModelInput(false);
    toast.success(`Model "${customModelIdInput.trim()}" disimpan untuk ${selectedAgent.name}.`);
  };

  const handleTestSelectedAgentModel = async () => {
    if (!selectedAgent) return;
    setModelTestStatus({ loading: true });
    const res = await testModelConnectionRemote({
      provider: selectedAgent.provider,
      model_id: selectedAgent.model_id,
    });
    setModelTestStatus({
      loading: false,
      ok: res.ok,
      message: res.ok
        ? `Koneksi ke ${getHumanModelInfo(selectedAgent.provider, selectedAgent.model_id).friendlyName} berhasil.`
        : res.error || "Koneksi belum berhasil. Periksa pengaturan token atau status server lokal.",
    });
  };

  // Evaluate availability warning for selected agent's provider/model (Section 4: never silently swap)
  const selectedProviderWarning = useMemo(() => {
    if (!selectedAgent) return null;
    const prov = selectedAgent.provider;
    if (prov === "ollama" && !engineHealth.ollama_online) {
      return {
        title: "Server AI Lokal (Ollama) belum aktif",
        message:
          "Agen ini menggunakan model Ollama lokal, tetapi layanan Ollama belum berjalan di perangkat Anda. Model pilihan Anda tetap disimpan dan tidak diganti secara diam-diam.",
        canGoToSettings: true,
      };
    }
    const pStatus = providerStatuses[prov];
    if (pStatus && !pStatus.is_local && !pStatus.has_saved_token) {
      return {
        title: `Penyedia ${pStatus.name} belum memiliki token API`,
        message:
          "Simpan token API untuk penyedia ini di menu Pengaturan → Model AI, atau pilih penyedia lain yang sudah terhubung.",
        canGoToSettings: true,
      };
    }
    return null;
  }, [selectedAgent, engineHealth.ollama_online, providerStatuses]);

  const affectedSubAgentsOnDelete = useMemo(() => {
    if (!agentPendingDelete) return [];
    return agents.filter((a) => a.parent_id === agentPendingDelete.id);
  }, [agentPendingDelete, agents]);

  const reparentSummary = useMemo(() => {
    if (!pendingReparent) return null;
    const child = agents.find((a) => a.id === pendingReparent.agentId);
    const newParent = agents.find((a) => a.id === pendingReparent.newParentId);
    const oldParent = agents.find((a) => a.id === child?.parent_id);
    if (!child || !newParent) return null;
    return { child, newParent, oldParent };
  }, [pendingReparent, agents]);

  const selectedModelMeta = selectedAgent
    ? getHumanModelInfo(selectedAgent.provider, selectedAgent.model_id)
    : null;

  const selectedAgentSubAgents = useMemo(() => {
    if (!selectedAgent) return [];
    return agents.filter((a) => a.parent_id === selectedAgent.id);
  }, [selectedAgent, agents]);

  return (
    <div className="flex-1 flex h-full overflow-hidden bg-[#191918]">
      {/* 1. Safe Agent Deletion Confirmation Dialog (Section 3 Interaksi diagram) */}
      <ConfirmDialog
        open={agentPendingDelete !== null}
        title={`Hapus agen "${agentPendingDelete?.name ?? ""}"?`}
        description="Apakah Anda yakin ingin menghapus agen pendukung ini dari Struktur Tim AI Anda?"
        impactNote={
          affectedSubAgentsOnDelete.length > 0
            ? `Dampak pada sub-agen: Terdapat ${affectedSubAgentsOnDelete.length} sub-agen di bawah agen ini (${affectedSubAgentsOnDelete.map((a) => a.name).join(", ")}). Sub-agen tersebut tidak akan terhapus dan akan otomatis dipindahkan ke bawah agen induk di atasnya. File hasil pekerjaan di Ruang Kerja tetap aman.`
            : "Dampak penghapusan: Agen ini akan dikeluarkan dari Struktur Tim AI. Seluruh file hasil pekerjaan di Ruang Kerja dan dokumen di Pengetahuan AKSA tetap aman."
        }
        confirmLabel="Ya, Hapus Agen"
        cancelLabel="Batal"
        destructive
        onCancel={() => setAgentPendingDelete(null)}
        onConfirm={() => {
          if (agentPendingDelete) {
            void deleteAgentNode(agentPendingDelete.id);
            toast.success(`Agen "${agentPendingDelete.name}" telah dihapus dari tim.`);
          }
          setAgentPendingDelete(null);
        }}
      />

      {/* 2. Parent Relationship Change Confirmation Dialog (Section 3: Tampilkan konfirmasi sebelum mengubah relasi) */}
      <ConfirmDialog
        open={reparentSummary !== null}
        title="Ubah hubungan delegasi agen?"
        description={
          reparentSummary
            ? `Pindahkan "${reparentSummary.child.name}" agar membantu "${reparentSummary.newParent.name}"?`
            : ""
        }
        impactNote={
          reparentSummary
            ? `Dampak alur kerja: Sebelumnya agen ini berada di bawah "${reparentSummary.oldParent?.name ?? "Koordinator Utama"}". Setelah diubah, "${reparentSummary.newParent.name}" akan menjadi induk yang mendelegasikan tugas kepada "${reparentSummary.child.name}".`
            : undefined
        }
        confirmLabel="Ya, Ubah Hubungan"
        cancelLabel="Batal"
        onCancel={() => setPendingReparent(null)}
        onConfirm={() => {
          if (pendingReparent) {
            void (async () => {
              const res = await reparentAgent(
                pendingReparent.agentId,
                pendingReparent.newParentId
              );
              if (res.ok) {
                toast.success("Hubungan hierarki agen berhasil diperbarui.");
              } else {
                toast.error(res.error || "Gagal memperbarui hubungan agen.");
              }
            })();
          }
          setPendingReparent(null);
        }}
      />

      {/* 3. Confirm before Automatic Recommendation overwrites Manual Model choice (Section 4) */}
      <ConfirmDialog
        open={pendingAutoOverwrite}
        title="Ganti pilihan model manual ke Rekomendasi Otomatis?"
        description={`Saat ini "${selectedAgent?.name ?? "Agen"}" menggunakan model yang Anda pilih sendiri (${selectedModelMeta?.friendlyName ?? selectedAgent?.model_id}).`}
        impactNote="Jika Anda beralih ke Otomatis, AKSA akan menyesuaikan model agen ini dengan rekomendasi terbaik untuk perannya. Anda tetap dapat kembali ke Pilih sendiri kapan saja."
        confirmLabel="Gunakan Rekomendasi Otomatis"
        cancelLabel="Pertahankan Pilihan Manual"
        onCancel={() => setPendingAutoOverwrite(false)}
        onConfirm={applyRecommendedModelNow}
      />

      {/* 4. Add New Agent Modal with Parent Selection (Section 3: Tambah agen; pilih induk yang akan dibantu) */}
      {addAgentModalParent && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="aksa-add-agent-modal-title"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4"
        >
          <div className="w-full max-w-lg rounded-2xl bg-[#21211F] border border-white/[0.12] shadow-2xl p-6 space-y-4">
            <div className="space-y-1">
              <h3 id="aksa-add-agent-modal-title" className="text-[18px] font-semibold text-zinc-100">
                Tambah Agen Pendukung Baru
              </h3>
              <p className="text-[13px] text-zinc-300">
                Pilih agen induk yang akan dibantu serta jenis pekerjaan untuk agen baru ini.
              </p>
            </div>

            <div className="space-y-3">
              <div>
                <label
                  htmlFor="aksa-new-agent-parent"
                  className="block text-xs font-semibold text-zinc-200 mb-1"
                >
                  Agen ini membantu (Pilih Agen Induk)
                </label>
                <select
                  id="aksa-new-agent-parent"
                  value={addAgentModalParent.id}
                  onChange={(e) => {
                    const found = agents.find((a) => a.id === e.target.value);
                    if (found) setAddAgentModalParent(found);
                  }}
                  className="w-full rounded-xl bg-[#262624] border border-white/[0.1] px-3 py-2 text-[13px] text-zinc-100"
                >
                  {agents.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name} ({a.parent_id === null ? "Asisten Utama" : `Tingkat ${a.tier_level + 1}`})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-200 mb-1.5">
                  Pilih Jenis Pekerjaan (Template)
                </label>
                <div className="grid grid-cols-2 gap-2">
                  {JOB_TEMPLATES.map((tpl) => (
                    <button
                      type="button"
                      key={tpl.id}
                      onClick={() => {
                        setNewAgentTemplateId(tpl.id);
                        if (!newAgentName.trim()) {
                          setNewAgentName(tpl.label);
                        }
                      }}
                      className={cn(
                        "rounded-xl p-2.5 text-left border transition-colors space-y-0.5",
                        newAgentTemplateId === tpl.id
                          ? "bg-[#D97757]/15 border-[#D97757] text-zinc-100"
                          : "bg-[#262624] border-white/[0.08] text-zinc-300 hover:text-white"
                      )}
                    >
                      <div className="text-xs font-semibold">{tpl.label}</div>
                      <div className="text-[11px] text-zinc-400 line-clamp-1">{tpl.roleTitle}</div>
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label
                  htmlFor="aksa-new-agent-custom-name"
                  className="block text-xs font-semibold text-zinc-200 mb-1"
                >
                  Nama Agen (Opsional)
                </label>
                <input
                  id="aksa-new-agent-custom-name"
                  type="text"
                  value={newAgentName}
                  onChange={(e) => setNewAgentName(e.target.value)}
                  placeholder="Contoh: Asisten Laporan Keuangan"
                  className="w-full rounded-xl bg-[#262624] border border-white/[0.1] px-3 py-2 text-[13px] text-zinc-100"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-white/[0.07]">
              <button
                type="button"
                onClick={() => setAddAgentModalParent(null)}
                className="rounded-xl bg-[#262624] hover:bg-zinc-700 border border-white/[0.1] px-4 py-2 text-[13px] font-medium text-zinc-200"
              >
                Batal
              </button>
              <button
                type="button"
                onClick={() => void handleConfirmCreateAgent()}
                className="rounded-xl bg-[#D97757] hover:bg-[#c96a4b] px-4 py-2 text-[13px] font-semibold text-white"
              >
                Buat Agen Pendukung
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Left Main Area: Visual Hierarchy Diagram Canvas OR Accessible Tree List */}
      <div className="flex-1 flex flex-col overflow-hidden p-5 md:p-6 min-w-0">
        {/* Top Page Header & Controls */}
        <div className="flex flex-wrap items-center justify-between gap-3 pb-4 mb-4 border-b border-white/[0.07]">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Network size={20} className="text-[#D97757]" />
              <h1 className="text-[21px] font-semibold tracking-tight text-zinc-100">
                Struktur Tim AI
              </h1>
            </div>
            <p className="text-[13px] text-zinc-300">
              Lihat hierarki delegasi tim AI Anda. Klik agen pada diagram untuk mengatur peran,
              kemampuan, dan model AI.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => handleOpenAddAgentModal()}
              className="flex items-center gap-1.5 rounded-xl bg-[#D97757] hover:bg-[#c96a4b] px-3.5 py-2 text-[13px] font-semibold text-white transition-colors shadow-sm"
            >
              <Plus size={15} />
              <span>Tambah Agen</span>
            </button>

            {viewMode === "diagram" && (
              <button
                type="button"
                onClick={() => {
                  void autoLayoutAgents();
                  toast.success("Tata letak diagram hierarki dirapikan.");
                }}
                title="Susun ulang posisi diagram hierarki secara otomatis"
                className="flex items-center gap-1.5 rounded-xl bg-[#21211F] hover:bg-[#262624] border border-white/[0.1] px-3 py-2 text-xs font-medium text-zinc-200 transition-colors"
              >
                <LayoutTemplate size={14} className="text-[#D97757]" />
                <span>Rapikan Diagram</span>
              </button>
            )}

            {/* Diagram vs List View Toggle (Section 3: Sediakan tampilan alternatif Daftar) */}
            <div
              role="group"
              aria-label="Pilihan tampilan struktur tim"
              className="flex items-center rounded-xl bg-[#21211F] border border-white/[0.09] p-1"
            >
              <button
                type="button"
                onClick={() => setViewMode("diagram")}
                className={cn(
                  "flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors",
                  viewMode === "diagram"
                    ? "bg-[#262624] text-zinc-100 shadow-sm"
                    : "text-zinc-400 hover:text-zinc-200"
                )}
              >
                <Network size={13} />
                <span>Diagram Hierarki</span>
              </button>
              <button
                type="button"
                onClick={() => setViewMode("list")}
                className={cn(
                  "flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors",
                  viewMode === "list"
                    ? "bg-[#262624] text-zinc-100 shadow-sm"
                    : "text-zinc-400 hover:text-zinc-200"
                )}
              >
                <ListTree size={13} />
                <span>Tampilan Daftar</span>
              </button>
            </div>
          </div>
        </div>

        {/* Main Content: Diagram Hierarki OR Daftar Hierarki */}
        {agents.length === 0 ? (
          <EmptyStateCard
            icon={<Network size={22} />}
            title="Belum ada agen di dalam tim"
            description="Buat agen pertama untuk mulai menyusun struktur tim AI Anda."
            actionLabel="Tambah Agen"
            onAction={() => handleOpenAddAgentModal()}
          />
        ) : viewMode === "diagram" ? (
          <div className="flex-1 rounded-2xl bg-[#141413] border border-white/[0.08] overflow-hidden relative flex flex-col">
            {/* Helper Legend Bar */}
            <div className="px-4 py-2 border-b border-white/[0.06] bg-[#21211F]/80 flex flex-wrap items-center justify-between gap-2 text-xs text-zinc-300 z-10">
              <div className="flex items-center gap-3 flex-wrap">
                <span className="inline-flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-[#D97757]" />
                  <span>Asisten Utama mendelegasikan tugas ke Agen Pendukung di bawahnya</span>
                </span>
              </div>
              <span className="text-zinc-400">
                {agents.length} agen terdaftar • Klik node untuk mengatur
              </span>
            </div>

            <div className="flex-1 relative">
              <ReactFlow
                nodes={flowNodes}
                edges={flowEdges}
                nodeTypes={nodeTypes}
                fitView
                fitViewOptions={{ padding: 0.22 }}
                minZoom={0.35}
                maxZoom={1.6}
                onConnect={handleConnectNodes}
                onNodeDragStop={(_evt, node) => {
                  void updateAgentConfig(node.id, {
                    position_x: Math.round(node.position.x),
                    position_y: Math.round(node.position.y),
                  });
                }}
                proOptions={{ hideAttribution: true }}
              >
                <Background color="rgba(156, 154, 146, 0.14)" gap={22} />
                <Controls showInteractive={false} />
                <MiniMap
                  pannable
                  zoomable
                  nodeColor={(n) =>
                    n.id === selectedAgent?.id
                      ? "#D97757"
                      : n.id === activeAgentId
                      ? "#10B981"
                      : "#52525B"
                  }
                />
              </ReactFlow>
            </div>
          </div>
        ) : (
          /* Accessible Hierarchical List View using the exact same live data */
          <div className="flex-1 rounded-2xl bg-[#141413] border border-white/[0.08] p-4 overflow-y-auto space-y-3">
            {agents
              .slice()
              .sort((a, b) => a.tier_level - b.tier_level)
              .map((agt) => {
                const badge = getProviderBadgeStyle(agt.provider);
                const modelMeta = getHumanModelInfo(agt.provider, agt.model_id);
                const isSelected = selectedAgent?.id === agt.id;
                const runtimeStatus = getAgentRuntimeStatus(agt.id);
                const parent = agents.find((p) => p.id === agt.parent_id);
                const children = agents.filter((c) => c.parent_id === agt.id);

                return (
                  <div
                    key={agt.id}
                    onClick={() => selectAgent(agt.id)}
                    style={{ marginLeft: `${Math.min(agt.tier_level * 24, 72)}px` }}
                    className={cn(
                      "rounded-2xl p-4 border cursor-pointer transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-4",
                      isSelected
                        ? "bg-[#262624] border-[#D97757] ring-1 ring-[#D97757]/30"
                        : "bg-[#21211F] border-white/[0.08] hover:border-white/[0.2]"
                    )}
                  >
                    <div className="space-y-1.5 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <StatusBadge
                          tone={agt.parent_id === null ? "accent" : "neutral"}
                          label={
                            agt.parent_id === null
                              ? "Asisten Utama (Root)"
                              : `Membantu: ${parent?.name ?? "Tim"}`
                          }
                        />
                        <span className="text-[15px] font-semibold text-zinc-100">{agt.name}</span>
                        <StatusBadge
                          tone={
                            runtimeStatus === "Bekerja"
                              ? "success"
                              : runtimeStatus === "Menunggu persetujuan"
                              ? "warning"
                              : "neutral"
                          }
                          label={runtimeStatus}
                        />
                      </div>
                      <p className="text-[13px] font-medium text-zinc-200">{agt.role_title}</p>
                      <p className="text-xs text-zinc-400 leading-relaxed">{agt.description}</p>
                      <div className="text-xs text-zinc-400 pt-0.5">
                        {agt.tool_categories.length} kemampuan aktif
                        {children.length > 0
                          ? ` • Mendelegasikan ke: ${children.map((c) => c.name).join(", ")}`
                          : ""}
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0 flex-wrap">
                      <span className="inline-flex items-center gap-1.5 rounded-xl bg-black/30 border border-white/[0.08] px-3 py-1.5 text-xs font-medium text-zinc-200">
                        <ProviderIcon provider={agt.provider} size={12} />
                        <span>
                          {modelMeta.friendlyName} ({badge.label})
                        </span>
                      </span>

                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleOpenAddAgentModal(agt);
                        }}
                        className="rounded-xl bg-white/[0.06] hover:bg-[#D97757]/20 hover:text-[#F09373] border border-white/[0.08] px-3 py-1.5 text-xs font-medium text-zinc-200 transition-colors"
                      >
                        + Sub-agen
                      </button>

                      {agt.parent_id !== null && (
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            setAgentPendingDelete(agt);
                          }}
                          aria-label={`Hapus ${agt.name}`}
                          title="Hapus agen ini"
                          className="rounded-xl p-2 text-zinc-400 hover:text-rose-300 hover:bg-rose-500/15 transition-colors"
                        >
                          <Trash2 size={15} />
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
          </div>
        )}
      </div>

      {/* Right Configuration Panel: 6 Clear Sections + Mode Sederhana/Lanjutan (Sections 3 & 4) */}
      {selectedAgent && (
        <aside
          aria-label="Panel Konfigurasi Agen"
          className="w-[410px] border-l border-white/[0.08] bg-[#1d1d1b] p-5 overflow-y-auto space-y-5 shrink-0"
        >
          {/* Panel Header & Simple/Advanced Mode Toggle */}
          <div className="space-y-3 pb-3 border-b border-white/[0.07]">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 min-w-0">
                <SlidersHorizontal size={17} className="text-[#D97757] shrink-0" />
                <div className="min-w-0">
                  <h2 className="text-[15px] font-semibold text-zinc-100 truncate">
                    {selectedAgent.name}
                  </h2>
                  <p className="text-xs text-zinc-400">
                    {selectedAgent.parent_id === null
                      ? "Asisten Utama (Root)"
                      : `Tingkat ${selectedAgent.tier_level + 1} • Agen Pendukung`}
                  </p>
                </div>
              </div>

              <button
                type="button"
                onClick={() => handleOpenAddAgentModal(selectedAgent)}
                className="flex items-center gap-1 rounded-xl bg-[#D97757]/15 hover:bg-[#D97757]/25 text-[#F09373] border border-[#D97757]/30 px-2.5 py-1.5 text-xs font-semibold transition-colors shrink-0"
              >
                <Plus size={13} />
                <span>Sub-agen</span>
              </button>
            </div>

            {/* Mode Sederhana (Default) vs Mode Lanjutan */}
            <div className="flex items-center justify-between rounded-xl bg-[#262624] border border-white/[0.08] p-1">
              <button
                type="button"
                onClick={() => setExperienceMode("sederhana")}
                className={cn(
                  "flex-1 rounded-lg py-1.5 text-xs font-semibold transition-colors",
                  experienceMode === "sederhana"
                    ? "bg-[#D97757] text-white shadow-sm"
                    : "text-zinc-300 hover:text-white"
                )}
              >
                Mode Sederhana
              </button>
              <button
                type="button"
                onClick={() => setExperienceMode("lanjutan")}
                className={cn(
                  "flex-1 rounded-lg py-1.5 text-xs font-semibold transition-colors",
                  experienceMode === "lanjutan"
                    ? "bg-[#D97757] text-white shadow-sm"
                    : "text-zinc-300 hover:text-white"
                )}
              >
                Mode Lanjutan
              </button>
            </div>
          </div>

          {/* BAGIAN 1: Identitas Agen */}
          <section className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-4 space-y-3">
            <h3 className="text-[13.5px] font-semibold text-zinc-100">1. Identitas Agen</h3>

            <div>
              <label className="block text-xs font-medium text-zinc-300 mb-1.5">
                Template Jenis Pekerjaan
              </label>
              <div className="grid grid-cols-2 gap-1.5">
                {JOB_TEMPLATES.map((tpl) => (
                  <button
                    key={tpl.id}
                    type="button"
                    onClick={() => handleApplyJobTemplate(tpl)}
                    className={cn(
                      "rounded-xl px-2.5 py-2 text-left text-xs font-medium border transition-colors",
                      selectedTemplateId === tpl.id
                        ? "bg-[#D97757]/15 border-[#D97757]/50 text-zinc-100"
                        : "bg-[#262624] border-white/[0.07] text-zinc-300 hover:text-white"
                    )}
                  >
                    {tpl.label}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label
                htmlFor="aksa-agent-name-input"
                className="block text-xs font-medium text-zinc-300 mb-1"
              >
                Nama Agen
              </label>
              <input
                id="aksa-agent-name-input"
                type="text"
                value={selectedAgent.name}
                onChange={(e) =>
                  void updateAgentConfig(selectedAgent.id, { name: e.target.value })
                }
                className="w-full rounded-xl bg-[#262624] border border-white/[0.09] px-3 py-2 text-[13px] text-zinc-100"
              />
            </div>

            <div>
              <label
                htmlFor="aksa-agent-role-input"
                className="block text-xs font-medium text-zinc-300 mb-1"
              >
                Peran Singkat
              </label>
              <input
                id="aksa-agent-role-input"
                type="text"
                value={selectedAgent.role_title}
                onChange={(e) =>
                  void updateAgentConfig(selectedAgent.id, { role_title: e.target.value })
                }
                className="w-full rounded-xl bg-[#262624] border border-white/[0.09] px-3 py-2 text-[13px] text-zinc-100"
              />
            </div>
          </section>

          {/* BAGIAN 2: Tanggung Jawab dan Instruksi */}
          <section className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-4 space-y-3">
            <h3 className="text-[13.5px] font-semibold text-zinc-100">
              2. Tanggung Jawab &amp; Instruksi
            </h3>

            <div>
              <label
                htmlFor="aksa-agent-desc-input"
                className="block text-xs font-medium text-zinc-300 mb-1"
              >
                Deskripsi Tanggung Jawab
              </label>
              <textarea
                id="aksa-agent-desc-input"
                rows={2}
                value={selectedAgent.description}
                onChange={(e) =>
                  void updateAgentConfig(selectedAgent.id, { description: e.target.value })
                }
                className="w-full rounded-xl bg-[#262624] border border-white/[0.09] p-2.5 text-[13px] text-zinc-200 leading-relaxed"
              />
            </div>

            {experienceMode === "lanjutan" && (
              <div>
                <label
                  htmlFor="aksa-agent-prompt-input"
                  className="block text-xs font-medium text-zinc-300 mb-1"
                >
                  Instruksi Kerja Agen (System Prompt)
                </label>
                <textarea
                  id="aksa-agent-prompt-input"
                  rows={3}
                  value={selectedAgent.system_prompt}
                  onChange={(e) =>
                    void updateAgentConfig(selectedAgent.id, { system_prompt: e.target.value })
                  }
                  className="w-full rounded-xl bg-[#262624] border border-white/[0.09] p-2.5 text-xs text-zinc-200 leading-relaxed"
                />
              </div>
            )}
          </section>

          {/* BAGIAN 3: Kemampuan (Tools, Aplikasi, Keahlian, Akses) */}
          <section className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-4 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-[13.5px] font-semibold text-zinc-100">
                3. Kemampuan &amp; Akses
              </h3>
              <span className="text-xs text-zinc-400">
                {selectedAgent.tool_categories.length} aktif
              </span>
            </div>

            <p className="text-xs text-zinc-400 leading-relaxed flex items-center gap-1.5">
              <ShieldCheck size={13} className="text-emerald-400 shrink-0" />
              <span>Agen hanya dapat memakai kemampuan yang Anda centang.</span>
            </p>

            <div className="flex items-center gap-1 p-1 rounded-xl bg-[#262624] border border-white/[0.07]">
              <button
                type="button"
                onClick={() => setToolsTab("core")}
                className={cn(
                  "flex-1 py-1.5 px-2 rounded-lg text-xs font-medium transition-colors text-center truncate",
                  toolsTab === "core"
                    ? "bg-[#D97757] text-white shadow-sm"
                    : "text-zinc-300 hover:text-white"
                )}
              >
                Alat ({Object.keys(TOOL_CATEGORY_LABELS).length})
              </button>
              <button
                type="button"
                onClick={() => setToolsTab("apps")}
                className={cn(
                  "flex-1 py-1.5 px-2 rounded-lg text-xs font-medium transition-colors text-center truncate",
                  toolsTab === "apps"
                    ? "bg-[#D97757] text-white shadow-sm"
                    : "text-zinc-300 hover:text-white"
                )}
              >
                Aplikasi ({connectedApps.length})
              </button>
              <button
                type="button"
                onClick={() => setToolsTab("skills")}
                className={cn(
                  "flex-1 py-1.5 px-2 rounded-lg text-xs font-medium transition-colors text-center truncate",
                  toolsTab === "skills"
                    ? "bg-[#D97757] text-white shadow-sm"
                    : "text-zinc-300 hover:text-white"
                )}
              >
                Keahlian ({installedSkills.length})
              </button>
            </div>

            {toolsTab === "core" && (
              <div className="space-y-1.5 pt-1 max-h-52 overflow-y-auto pr-1">
                {Object.entries(TOOL_CATEGORY_LABELS).map(([key, label]) => {
                  const checked = selectedAgent.tool_categories.includes(key);
                  return (
                    <button
                      key={key}
                      type="button"
                      onClick={() => toggleToolCategory(key)}
                      className={cn(
                        "w-full flex items-start justify-between gap-2 rounded-xl px-3 py-2 text-xs border transition-colors text-left",
                        checked
                          ? "bg-white/[0.07] border-[#D97757]/50 text-zinc-100"
                          : "bg-[#262624] border-white/[0.06] text-zinc-300 hover:text-white"
                      )}
                    >
                      <div className="space-y-0.5">
                        <div className="inline-flex items-center gap-2 font-semibold">
                          <ToolCategoryIcon category={key} size={13} />
                          <span>{label}</span>
                        </div>
                        <p className="text-[11.5px] text-zinc-400 pl-5">
                          {TOOL_CATEGORY_DESCRIPTIONS[key]}
                        </p>
                      </div>
                      {checked && <Check size={14} className="text-[#D97757] shrink-0 mt-0.5" />}
                    </button>
                  );
                })}
              </div>
            )}

            {toolsTab === "apps" && (
              <div className="space-y-1.5 pt-1">
                {connectedApps.length > 0 ? (
                  connectedApps.map((app) => {
                    const checked = isAppAllowed(app.id);
                    return (
                      <button
                        key={app.id}
                        type="button"
                        onClick={() => toggleAppPermission(app.id)}
                        className={cn(
                          "w-full flex items-center justify-between rounded-xl px-3 py-2 text-xs border transition-colors text-left",
                          checked
                            ? "bg-white/[0.07] border-[#D97757]/50 text-zinc-100"
                            : "bg-[#262624] border-white/[0.06] text-zinc-300 hover:text-white"
                        )}
                      >
                        <div className="inline-flex items-center gap-2 min-w-0">
                          {getAppCategoryIcon(app.category_label)}
                          <span className="font-medium truncate text-zinc-100">
                            {app.display_name}
                          </span>
                        </div>
                        {checked && <Check size={14} className="text-[#D97757] shrink-0 ml-2" />}
                      </button>
                    );
                  })
                ) : (
                  <div className="p-3 rounded-xl bg-[#262624] border border-white/[0.06] text-center space-y-1">
                    <ShieldAlert className="w-4 h-4 text-amber-400 mx-auto" />
                    <p className="text-xs font-medium text-zinc-200">
                      Belum Ada Aplikasi Terhubung
                    </p>
                    <p className="text-xs text-zinc-400">
                      Izinkan aplikasi di menu <strong>Aplikasi</strong> terlebih dahulu.
                    </p>
                  </div>
                )}
              </div>
            )}

            {toolsTab === "skills" && (
              <div className="space-y-1.5 pt-1">
                {installedSkills.length > 0 ? (
                  installedSkills.map((skill) => {
                    const checked = isSkillAssigned(skill.skill_id);
                    return (
                      <button
                        key={skill.id}
                        type="button"
                        onClick={() => toggleSkillAssignment(skill.skill_id)}
                        className={cn(
                          "w-full flex items-center justify-between rounded-xl px-3 py-2 text-xs border transition-colors text-left",
                          checked
                            ? "bg-white/[0.07] border-[#D97757]/50 text-zinc-100"
                            : "bg-[#262624] border-white/[0.06] text-zinc-300 hover:text-white"
                        )}
                      >
                        <div className="inline-flex items-center gap-2 min-w-0">
                          <Sparkles size={13} className="text-[#D97757] shrink-0" />
                          <span className="font-medium truncate text-zinc-100">
                            {skill.display_name}
                          </span>
                        </div>
                        {checked && <Check size={14} className="text-[#D97757] shrink-0 ml-2" />}
                      </button>
                    );
                  })
                ) : (
                  <div className="p-3 rounded-xl bg-[#262624] border border-white/[0.06] text-center space-y-1">
                    <Sparkles className="w-4 h-4 text-[#D97757] mx-auto" />
                    <p className="text-xs font-medium text-zinc-200">
                      Belum Ada Keahlian Terpasang
                    </p>
                  </div>
                )}
              </div>
            )}
          </section>

          {/* BAGIAN 4: Model AI — Otomatis (direkomendasikan) DAN Pilih sendiri (Manual) (Section 4 P0) */}
          <section className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-4 space-y-3.5">
            <div className="flex items-center justify-between">
              <h3 className="text-[13.5px] font-semibold text-zinc-100">4. Model AI</h3>
              <StatusBadge
                tone={selectedAgent.model_selection_mode === "manual" ? "accent" : "success"}
                label={
                  selectedAgent.model_selection_mode === "manual"
                    ? "Pilihan Manual"
                    : "Otomatis"
                }
              />
            </div>

            {/* Explicit Auto vs Manual Mode Selector — ALWAYS accessible in both Simple & Advanced Mode */}
            <div
              role="radiogroup"
              aria-label="Cara pemilihan model AI"
              className="grid grid-cols-2 gap-2"
            >
              <button
                type="button"
                role="radio"
                aria-checked={selectedAgent.model_selection_mode !== "manual"}
                onClick={() => handleSelectModelMode("auto")}
                className={cn(
                  "rounded-xl p-2.5 border text-left transition-all space-y-0.5",
                  selectedAgent.model_selection_mode !== "manual"
                    ? "bg-[#D97757]/15 border-[#D97757] text-zinc-100"
                    : "bg-[#262624] border-white/[0.08] text-zinc-300 hover:text-white"
                )}
              >
                <div className="flex items-center gap-1.5 text-xs font-semibold">
                  <Wand2 size={13} className="text-[#D97757]" />
                  <span>Otomatis</span>
                </div>
                <p className="text-[11px] text-zinc-400">Direkomendasikan sesuai tugas</p>
              </button>

              <button
                type="button"
                role="radio"
                aria-checked={selectedAgent.model_selection_mode === "manual"}
                onClick={() => handleSelectModelMode("manual")}
                className={cn(
                  "rounded-xl p-2.5 border text-left transition-all space-y-0.5",
                  selectedAgent.model_selection_mode === "manual"
                    ? "bg-[#D97757]/15 border-[#D97757] text-zinc-100"
                    : "bg-[#262624] border-white/[0.08] text-zinc-300 hover:text-white"
                )}
              >
                <div className="flex items-center gap-1.5 text-xs font-semibold">
                  <Edit3 size={13} className="text-[#D97757]" />
                  <span>Pilih sendiri</span>
                </div>
                <p className="text-[11px] text-zinc-400">Pilih penyedia &amp; model manual</p>
              </button>
            </div>

            {/* Manual Provider & Model Selectors (Always visible when Pilih sendiri is active, or user can switch directly) */}
            <div className="space-y-3 pt-1">
              <div>
                <label
                  htmlFor="aksa-agent-provider-select"
                  className="block text-xs font-medium text-zinc-300 mb-1"
                >
                  Penyedia AI
                </label>
                <select
                  id="aksa-agent-provider-select"
                  value={selectedAgent.provider}
                  onChange={(e) => handleManualProviderChange(e.target.value as ModelProvider)}
                  className="w-full rounded-xl bg-[#262624] border border-white/[0.1] px-3 py-2 text-xs text-zinc-100"
                >
                  {PROVIDER_LIST.map((prov) => {
                    const pStat = providerStatuses[prov.id];
                    const statusLabel = prov.isLocal
                      ? prov.id === "ollama" && engineHealth.ollama_online
                        ? "Aktif di Perangkat"
                        : "Lokal"
                      : pStat?.has_saved_token
                      ? "Token Tersimpan"
                      : "Belum Dihubungkan";
                    return (
                      <option key={prov.id} value={prov.id}>
                        {prov.label} — {statusLabel}
                      </option>
                    );
                  })}
                </select>
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <label
                    htmlFor="aksa-agent-model-select"
                    className="block text-xs font-medium text-zinc-300"
                  >
                    Model AI
                  </label>
                  <button
                    type="button"
                    onClick={() => {
                      setShowCustomModelInput((v) => !v);
                      setCustomModelIdInput(selectedAgent.model_id);
                    }}
                    className="text-[11.5px] text-[#D97757] hover:underline"
                  >
                    {showCustomModelInput ? "Pilih dari daftar" : "Masukkan ID model khusus"}
                  </button>
                </div>

                {!showCustomModelInput ? (
                  <select
                    id="aksa-agent-model-select"
                    value={selectedAgent.model_id}
                    onChange={(e) => handleManualModelChange(e.target.value)}
                    className="w-full rounded-xl bg-[#262624] border border-white/[0.1] px-3 py-2 text-xs text-zinc-100"
                  >
                    {availableModelsForProvider.map((m) => (
                      <option key={m.model_id} value={m.model_id}>
                        {m.friendlyName} ({m.costTierLabel})
                      </option>
                    ))}
                    <option value="__custom__">+ Masukkan ID Model Lainnya…</option>
                  </select>
                ) : (
                  <div className="flex gap-1.5">
                    <input
                      type="text"
                      aria-label="ID Model Kustom"
                      value={customModelIdInput}
                      onChange={(e) => setCustomModelIdInput(e.target.value)}
                      placeholder="Contoh: gemini-4-carbon"
                      className="flex-1 rounded-xl bg-[#262624] border border-white/[0.1] px-3 py-1.5 text-xs text-zinc-100 font-mono"
                    />
                    <button
                      type="button"
                      onClick={handleApplyCustomModelId}
                      className="rounded-xl bg-[#D97757] hover:bg-[#c96a4b] px-3 py-1.5 text-xs font-semibold text-white"
                    >
                      Pakai
                    </button>
                  </div>
                )}
              </div>

              {/* Human-Readable Model Summary Card (Section 4: kemampuan, konteks, biaya/kuota, dukungan tool calling) */}
              {selectedModelMeta && (
                <div className="rounded-xl bg-[#262624] border border-white/[0.07] p-3 space-y-1.5 text-xs">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-semibold text-zinc-100">
                      {selectedModelMeta.friendlyName}
                    </span>
                    <span className="rounded bg-[#D97757]/15 border border-[#D97757]/30 px-2 py-0.5 text-[11px] text-[#F09373]">
                      {selectedModelMeta.costTierLabel}
                    </span>
                  </div>
                  <p className="text-zinc-300 leading-relaxed">
                    {selectedModelMeta.capabilitiesLabel}
                  </p>
                  <div className="flex flex-wrap items-center justify-between gap-2 pt-1 border-t border-white/[0.06] text-[11.5px] text-zinc-400">
                    <span>{selectedModelMeta.contextWindowLabel}</span>
                    <span>
                      {selectedModelMeta.supportsToolCalling
                        ? "Mendukung pemanggilan alat/fungsi"
                        : "Fokus penalaran teks"}
                    </span>
                  </div>
                </div>
              )}

              {/* Provider / Model Availability Warning without silent replacement (Section 4) */}
              {selectedProviderWarning && (
                <div
                  role="alert"
                  className="rounded-xl bg-amber-500/10 border border-amber-500/30 p-3 space-y-2 text-xs text-amber-200"
                >
                  <div className="flex items-start gap-2">
                    <AlertTriangle size={15} className="text-amber-400 shrink-0 mt-0.5" />
                    <div className="space-y-1">
                      <div className="font-semibold">{selectedProviderWarning.title}</div>
                      <p className="leading-relaxed text-zinc-200">
                        {selectedProviderWarning.message}
                      </p>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2 pl-5">
                    <button
                      type="button"
                      onClick={() => setActiveNav("pengaturan")}
                      className="rounded-lg bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/40 px-2.5 py-1 text-xs font-semibold text-amber-200"
                    >
                      Atur Token Penyedia
                    </button>
                    {engineHealth.ollama_online && selectedAgent.provider !== "ollama" && (
                      <button
                        type="button"
                        onClick={() => handleManualProviderChange("ollama")}
                        className="rounded-lg bg-white/[0.08] hover:bg-white/[0.14] px-2.5 py-1 text-xs text-zinc-200"
                      >
                        Gunakan AI Lokal yang Aktif
                      </button>
                    )}
                  </div>
                </div>
              )}

              {/* Test Model Connection Button (Section 4 #7) */}
              <div className="flex items-center justify-between gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => void handleTestSelectedAgentModel()}
                  disabled={modelTestStatus?.loading}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-[#262624] hover:bg-zinc-700 border border-white/[0.1] px-3 py-1.5 text-xs font-medium text-zinc-200 transition-colors"
                >
                  <Play size={12} className={modelTestStatus?.loading ? "animate-spin" : ""} />
                  <span>{modelTestStatus?.loading ? "Menguji model..." : "Uji Koneksi Model"}</span>
                </button>

                {providerStatuses[selectedAgent.provider] && (
                  <span className="text-[11.5px] text-zinc-400">
                    Status:{" "}
                    {
                      formatProviderTokenStatus(
                        providerStatuses[selectedAgent.provider].token_status,
                        providerStatuses[selectedAgent.provider].is_local
                      ).label
                    }
                  </span>
                )}
              </div>

              {modelTestStatus && !modelTestStatus.loading && (
                <div
                  className={cn(
                    "rounded-xl p-2.5 text-xs flex items-start gap-2 border",
                    modelTestStatus.ok
                      ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-200"
                      : "bg-rose-500/10 border-rose-500/30 text-rose-200"
                  )}
                >
                  {modelTestStatus.ok ? (
                    <CheckCircle2 size={14} className="text-emerald-400 shrink-0 mt-0.5" />
                  ) : (
                    <AlertTriangle size={14} className="text-rose-400 shrink-0 mt-0.5" />
                  )}
                  <span>{modelTestStatus.message}</span>
                </div>
              )}
            </div>
          </section>

          {/* BAGIAN 5: Hubungan dengan Agen Lain (Section 3 Panel konfigurasi agen #5) */}
          <section className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-4 space-y-3">
            <div className="flex items-center gap-2">
              <GitBranch size={15} className="text-[#D97757]" />
              <h3 className="text-[13.5px] font-semibold text-zinc-100">
                5. Hubungan dengan Agen Lain
              </h3>
            </div>

            {selectedAgent.parent_id === null ? (
              <div className="rounded-xl bg-[#262624] border border-white/[0.07] p-3 text-xs text-zinc-300 leading-relaxed">
                <strong>Asisten Utama (Root):</strong> Agen ini berada di puncak hierarki, menerima
                instruksi Anda secara langsung, dan mendelegasikan tugas ke agen pendukung di
                bawahnya.
              </div>
            ) : (
              <div>
                <label
                  htmlFor="aksa-agent-parent-select"
                  className="block text-xs font-medium text-zinc-300 mb-1"
                >
                  Agen ini membantu (Pilih Agen Induk)
                </label>
                <select
                  id="aksa-agent-parent-select"
                  value={selectedAgent.parent_id}
                  onChange={(e) => handleRequestReparent(selectedAgent.id, e.target.value)}
                  className="w-full rounded-xl bg-[#262624] border border-white/[0.1] px-3 py-2 text-xs text-zinc-100"
                >
                  {agents
                    .filter((a) => a.id !== selectedAgent.id)
                    .map((candidate) => {
                      const isCycle = wouldCreateAgentCycle(
                        agents,
                        selectedAgent.id,
                        candidate.id
                      );
                      return (
                        <option
                          key={candidate.id}
                          value={candidate.id}
                          disabled={isCycle}
                        >
                          {candidate.name}{" "}
                          {candidate.parent_id === null
                            ? "(Asisten Utama)"
                            : `(Tingkat ${candidate.tier_level + 1})`}
                          {isCycle ? " — [Tidak valid: Sub-agen di bawahnya]" : ""}
                        </option>
                      );
                    })}
                </select>
              </div>
            )}

            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-xs text-zinc-300">
                <span>Sub-agen di bawah {selectedAgent.name}:</span>
                <span className="font-semibold">{selectedAgentSubAgents.length} sub-agen</span>
              </div>
              {selectedAgentSubAgents.length > 0 ? (
                <div className="flex flex-wrap gap-1.5">
                  {selectedAgentSubAgents.map((sub) => (
                    <button
                      type="button"
                      key={sub.id}
                      onClick={() => selectAgent(sub.id)}
                      className="rounded-lg bg-[#262624] hover:bg-white/[0.08] border border-white/[0.08] px-2.5 py-1 text-xs text-zinc-200 transition-colors"
                    >
                      {sub.name} →
                    </button>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-zinc-400">
                  Belum ada sub-agen di bawah agen ini.
                </p>
              )}
            </div>
          </section>

          {/* BAGIAN 6: Pengaturan Lanjutan (Section 3 Panel konfigurasi agen #6) */}
          <section className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-4 space-y-3">
            <button
              type="button"
              onClick={() => setShowAdvancedAccordion((v) => !v)}
              className="w-full flex items-center justify-between text-left"
            >
              <span className="text-[13.5px] font-semibold text-zinc-100">
                6. Pengaturan Lanjutan
              </span>
              {experienceMode === "lanjutan" || showAdvancedAccordion ? (
                <ChevronDown size={15} className="text-zinc-400" />
              ) : (
                <ChevronRight size={15} className="text-zinc-400" />
              )}
            </button>

            {(experienceMode === "lanjutan" || showAdvancedAccordion) && (
              <div className="space-y-3 pt-2 border-t border-white/[0.07] text-xs">
                <div className="space-y-1">
                  <div className="flex justify-between">
                    <span className="text-zinc-300">Temperatur (Kreativitas Respons)</span>
                    <span className="font-mono text-zinc-200">{selectedAgent.temperature}</span>
                  </div>
                  <input
                    type="range"
                    min={0}
                    max={1}
                    step={0.1}
                    aria-label="Temperatur model"
                    value={selectedAgent.temperature}
                    onChange={(e) =>
                      void updateAgentConfig(selectedAgent.id, {
                        temperature: parseFloat(e.target.value),
                      })
                    }
                    className="w-full accent-[#D97757]"
                  />
                </div>

                <div>
                  <label
                    htmlFor="aksa-agent-max-tokens"
                    className="block text-zinc-300 mb-1"
                  >
                    Batas Maksimum Token Respons
                  </label>
                  <input
                    id="aksa-agent-max-tokens"
                    type="number"
                    min={256}
                    max={32768}
                    step={256}
                    value={selectedAgent.max_tokens}
                    onChange={(e) =>
                      void updateAgentConfig(selectedAgent.id, {
                        max_tokens: Math.max(256, parseInt(e.target.value || "2048", 10)),
                      })
                    }
                    className="w-full rounded-xl bg-[#262624] border border-white/[0.09] px-3 py-1.5 font-mono text-zinc-100"
                  />
                </div>

                <div className="rounded-xl bg-[#262624] border border-white/[0.06] p-2.5 space-y-1 font-mono text-[11px] text-zinc-400">
                  <div>ID Agen: {selectedAgent.id}</div>
                  <div>ID Model Teknis: {selectedAgent.model_id}</div>
                  <div>Penyedia Teknis: {selectedAgent.provider}</div>
                </div>
              </div>
            )}
          </section>

          {/* Save & Delete Actions */}
          <div className="pt-2 space-y-2.5">
            <button
              type="button"
              onClick={() => {
                void updateAgentConfig(selectedAgent.id, {
                  name: selectedAgent.name,
                  role_title: selectedAgent.role_title,
                  description: selectedAgent.description,
                  provider: selectedAgent.provider,
                  model_id: selectedAgent.model_id,
                  model_selection_mode: selectedAgent.model_selection_mode,
                });
                toast.success(`Konfigurasi agen "${selectedAgent.name}" berhasil disimpan.`);
              }}
              className="w-full flex items-center justify-center gap-2 rounded-xl bg-[#D97757] hover:bg-[#c96a4b] py-2.5 text-[13px] font-semibold text-white transition-colors"
            >
              <Save size={14} />
              <span>Simpan Konfigurasi Agen</span>
            </button>

            {selectedAgent.parent_id !== null ? (
              <button
                type="button"
                onClick={() => setAgentPendingDelete(selectedAgent)}
                className="w-full flex items-center justify-center gap-1.5 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/30 py-2.5 text-xs font-semibold text-rose-300 transition-colors"
              >
                <Trash2 size={14} />
                <span>Hapus Agen Ini</span>
              </button>
            ) : (
              <p className="text-xs text-zinc-400 text-center flex items-center justify-center gap-1.5">
                <Info size={12} />
                <span>Asisten Utama adalah root tim dan tidak dapat dihapus.</span>
              </p>
            )}
          </div>
        </aside>
      )}
    </div>
  );
};
