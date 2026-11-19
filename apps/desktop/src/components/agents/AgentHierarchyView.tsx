import React, { useMemo, useState, useEffect } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  Handle,
  Position,
  type Node,
  type Edge,
  type NodeProps,
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
} from "lucide-react";
import { toast } from "sonner";
import { useAksaStore } from "@/stores/useAksaStore";
import {
  cn,
  getProviderBadgeStyle,
  TOOL_CATEGORY_LABELS,
  TOOL_CATEGORY_DESCRIPTIONS,
} from "@/lib/utils";
import { ProviderIcon, ToolCategoryIcon } from "@/components/ui/DynamicIcon";
import { ConfirmDialog, EmptyStateCard, StatusBadge } from "@/components/ui/UXPrimitives";
import type { AgentNodeConfig, ModelProvider, DesktopApp, SkillItem } from "@/types/aksa";
import { fetchDesktopAppsRemote, fetchSkillsRemote } from "@/services/engineClient";

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
    recommendedLabel: "Ollama Qwen 3.8 8B (Hemat Kuota & Privasi Lokal)",
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
    label: "Agent khusus",
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

const BASE_MODEL_PRESETS: { provider: ModelProvider; model_id: string; label: string }[] = [
  { provider: "gemini", model_id: "gemini-4-carbon", label: "[Cloud] Google Gemini • Gemini 4 Carbon (Manajer & Strategi)" },
  { provider: "gemini", model_id: "gemini-4-argon", label: "[Cloud] Google Gemini • Gemini 4 Argon (Multimodal & Agen)" },
  { provider: "gemini", model_id: "gemini-4-hydrogen", label: "[Cloud] Google Gemini • Gemini 4 Hydrogen (Cepat & Efisien)" },
  { provider: "gemini", model_id: "gemini-3.8-flash", label: "[Cloud] Google Gemini • Gemini 3.8 Flash (Responsif Harian)" },
  { provider: "gemini", model_id: "gemini-3.5-flash-lite", label: "[Cloud] Google Gemini • Gemini 3.5 Flash-Lite (Hemat Kuota)" },
  { provider: "anthropic", model_id: "claude-fable-5-2", label: "[Cloud] Anthropic • Claude Fable 5.2 (Penalaran Mendalam)" },
  { provider: "anthropic", model_id: "claude-opus-5-5", label: "[Cloud] Anthropic • Claude Opus 5.5 (Pengetahuan & Dokumen)" },
  { provider: "anthropic", model_id: "claude-sonnet-5-5", label: "[Cloud] Anthropic • Claude Sonnet 5.5 (Agen & Kontrol Aplikasi)" },
  { provider: "anthropic", model_id: "claude-haiku-5-5", label: "[Cloud] Anthropic • Claude Haiku 5.5 (Ringkas & Cepat)" },
  { provider: "openai", model_id: "gpt-6.2-astra", label: "[Cloud] OpenAI • GPT-6.2 Astra (Penalaran & Agen)" },
  { provider: "openai", model_id: "gpt-6.2-sol", label: "[Cloud] OpenAI • GPT-6.2 Sol (Seimbang & Stabil)" },
  { provider: "openai", model_id: "gpt-6.1-sol", label: "[Cloud] OpenAI • GPT-6.1 Sol (Produktivitas Kantor)" },
  { provider: "openai", model_id: "gpt-6-luna", label: "[Cloud] OpenAI • GPT-6 Luna (Hemat Biaya)" },
  { provider: "deepseek", model_id: "deepseek-v4-pro", label: "[Cloud] DeepSeek • DeepSeek V4 Pro (Analisis Data & Kode)" },
  { provider: "deepseek", model_id: "deepseek-flash", label: "[Cloud] DeepSeek • DeepSeek V4.1 Flash (Hemat untuk Excel)" },
  { provider: "deepseek", model_id: "deepseek-chat", label: "[Cloud] DeepSeek • DeepSeek Chat (Standar Dokumen)" },
  { provider: "deepseek", model_id: "deepseek-reasoner", label: "[Cloud] DeepSeek • DeepSeek R1 / Reasoner (Logika Mendalam)" },
  { provider: "groq", model_id: "meta-llama/llama-4-maverick-17b-128e-instruct", label: "[Cloud] Groq • Llama 4 Maverick 17B" },
  { provider: "groq", model_id: "meta-llama/llama-4-scout-17b-16e-instruct", label: "[Cloud] Groq • Llama 4 Scout 17B" },
  { provider: "groq", model_id: "qwen/qwen3-32b", label: "[Cloud] Groq • Qwen 3.8 / 3 32B" },
  { provider: "groq", model_id: "deepseek-r1-distill-llama-70b", label: "[Cloud] Groq • DeepSeek R1 Distill 70B" },
  { provider: "openrouter", model_id: "anthropic/claude-opus-5-5", label: "[Cloud] OpenRouter • Claude Opus 5.5" },
  { provider: "openrouter", model_id: "anthropic/claude-sonnet-5-5", label: "[Cloud] OpenRouter • Claude Sonnet 5.5" },
  { provider: "openrouter", model_id: "google/gemini-4-carbon", label: "[Cloud] OpenRouter • Gemini 4 Carbon" },
  { provider: "openrouter", model_id: "openai/gpt-6.2-astra", label: "[Cloud] OpenRouter • OpenAI GPT-6.2 Astra" },
  { provider: "openrouter", model_id: "deepseek/deepseek-v4-pro", label: "[Cloud] OpenRouter • DeepSeek V4 Pro" },
  { provider: "openrouter", model_id: "openrouter/auto", label: "[Cloud] OpenRouter • Rute Otomatis" },
  { provider: "ollama", model_id: "qwen3.8:8b", label: "[Lokal] Ollama • Qwen 3.8 8B (Rekomendasi Utama Indonesia)" },
  { provider: "ollama", model_id: "qwen3.8:14b", label: "[Lokal] Ollama • Qwen 3.8 14B (Akurasi Tinggi Lokal)" },
  { provider: "ollama", model_id: "qwen3-coder:30b", label: "[Lokal] Ollama • Qwen 3 Coder 30B" },
  { provider: "ollama", model_id: "gemma4:12b", label: "[Lokal] Ollama • Google Gemma 4 12B" },
  { provider: "ollama", model_id: "deepseek-r1:8b", label: "[Lokal] Ollama • DeepSeek R1 8B" },
  { provider: "ollama", model_id: "llama4:scout", label: "[Lokal] Ollama • Meta Llama 4 Scout" },
  { provider: "lmstudio", model_id: "qwen3.8-8b-instruct", label: "[Lokal] LM Studio • Qwen 3.8 8B Instruct" },
  { provider: "lmstudio", model_id: "gemma-4-12b-it", label: "[Lokal] LM Studio • Google Gemma 4 12B Instruct" },
  { provider: "lmstudio", model_id: "deepseek-r1-distill-qwen-14b", label: "[Lokal] LM Studio • DeepSeek R1 Distill 14B" },
];

type AgentFlowNodeData = {
  agent: AgentNodeConfig;
  isSelected: boolean;
  isActive: boolean;
  activeStepLabel?: string | null;
  onSelect: (id: string) => void;
  onAddChild: (agent: AgentNodeConfig) => void;
};

const AgentCustomFlowNode: React.FC<NodeProps<Node<AgentFlowNodeData>>> = ({ data }) => {
  const { agent, isSelected, isActive, activeStepLabel, onSelect, onAddChild } = data;
  const badge = getProviderBadgeStyle(agent.provider);

  return (
    <div
      onClick={() => onSelect(agent.id)}
      className={cn(
        "w-[300px] rounded-2xl p-4 cursor-pointer transition-all border text-left space-y-2.5 shadow-xl select-none relative",
        isActive
          ? "bg-[#212921] border-emerald-500 ring-2 ring-emerald-500/40 shadow-[0_0_30px_rgba(16,185,129,0.3)] animate-pulse"
          : isSelected
          ? "bg-[#262624] border-[#D97757] ring-2 ring-[#D97757]/25"
          : "bg-[#21211F] border-white/[0.1] hover:border-white/[0.22]"
      )}
    >
      {agent.parent_id && (
        <Handle
          type="target"
          position={Position.Top}
          className="!w-2.5 !h-2.5 !bg-[#D97757] !border-none"
        />
      )}

      {isActive && (
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 text-xs font-semibold">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
          <span className="truncate">{activeStepLabel || "Sedang Bekerja..."}</span>
        </div>
      )}

      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <span className="rounded bg-white/[0.08] px-1.5 py-0.5 text-[11px] font-semibold text-zinc-200">
              Tingkat {agent.tier_level + 1}
            </span>
            <span className="text-[13.5px] font-semibold text-zinc-100 truncate">{agent.name}</span>
          </div>
          <p className="text-xs text-zinc-300 truncate mt-0.5">{agent.role_title}</p>
        </div>

        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onAddChild(agent);
          }}
          title="Tambah Agen Pendukung di bawah agen ini"
          className="flex items-center gap-1 rounded-lg bg-white/[0.06] hover:bg-[#D97757]/20 hover:text-[#D97757] border border-white/[0.08] px-2 py-1 text-[11px] font-medium text-zinc-200 transition-colors shrink-0"
        >
          <Plus size={11} /> Agen Pendukung
        </button>
      </div>

      <div className="flex items-center justify-between rounded-xl bg-black/35 border border-white/[0.06] px-2.5 py-1.5">
        <div className="flex items-center gap-1.5 truncate">
          {badge.isLocal ? (
            <Cpu size={12} className="text-emerald-400 shrink-0" />
          ) : (
            <Cloud size={12} className="text-[#D97757] shrink-0" />
          )}
          <span className="text-xs font-medium text-zinc-200 truncate">{agent.model_id}</span>
        </div>
        <span
          className={cn(
            "rounded px-1.5 py-0.5 text-[10px] font-semibold border shrink-0",
            badge.badgeClass
          )}
        >
          {badge.label}
        </span>
      </div>

      <div className="flex flex-wrap gap-1">
        {agent.tool_categories.slice(0, 3).map((cat) => (
          <span
            key={cat}
            className="inline-flex items-center gap-1 rounded-md bg-white/[0.04] border border-white/[0.06] px-1.5 py-0.5 text-[10.5px] text-zinc-300"
          >
            <ToolCategoryIcon category={cat} size={11} />
            <span>{TOOL_CATEGORY_LABELS[cat] ?? cat}</span>
          </span>
        ))}
        {agent.tool_categories.length > 3 && (
          <span className="rounded-md bg-white/[0.04] px-1.5 py-0.5 text-[10.5px] text-zinc-400">
            +{agent.tool_categories.length - 3} kemampuan
          </span>
        )}
      </div>

      <Handle
        type="source"
        position={Position.Bottom}
        className="!w-2.5 !h-2.5 !bg-emerald-400 !border-none"
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
    deleteAgentNode,
    engineHealth,
    activeAgentId,
    activeAgentStep,
  } = useAksaStore();

  // Section 5.4: Make Simple Mode ("sederhana") the default experience, with full Advanced Mode ("lanjutan") toggle
  const [experienceMode, setExperienceMode] = useState<"sederhana" | "lanjutan">("sederhana");
  const [viewMode, setViewMode] = useState<"canvas" | "list">("canvas");
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>("asisten_dokumen");
  const [isCustomMode, setIsCustomMode] = useState(false);
  const [customModelId, setCustomModelId] = useState("");
  const [customProvider, setCustomProvider] = useState<ModelProvider>("gemini");
  const [connectedApps, setConnectedApps] = useState<DesktopApp[]>([]);
  const [installedSkills, setInstalledSkills] = useState<SkillItem[]>([]);
  const [toolsTab, setToolsTab] = useState<"core" | "apps" | "skills">("core");
  const [agentPendingDelete, setAgentPendingDelete] = useState<AgentNodeConfig | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const apps = await fetchDesktopAppsRemote();
        if (apps) {
          setConnectedApps(apps.filter((a) => a.is_connected));
        }
      } catch {}
      try {
        const skillsData = await fetchSkillsRemote();
        if (skillsData?.installed_skills) {
          setInstalledSkills(skillsData.installed_skills);
        }
      } catch {}
    })();
  }, []);

  const activeTeam = teams.find((t) => t.id === activeTeamId) ?? teams[0];
  const agents = activeTeam?.agents ?? [];
  const selectedAgent = agents.find((a) => a.id === selectedAgentId) ?? agents[0] ?? null;

  const allPresets = useMemo(() => {
    const list = [...BASE_MODEL_PRESETS];
    if (engineHealth.ollama_online && engineHealth.ollama_models.length > 0) {
      for (const m of engineHealth.ollama_models) {
        list.unshift({
          provider: "ollama",
          model_id: m,
          label: `[Lokal Aktif] Ollama • ${m}`,
        });
      }
    }
    return list;
  }, [engineHealth.ollama_online, engineHealth.ollama_models]);

  const flowNodes: Node<AgentFlowNodeData>[] = useMemo(
    () =>
      agents.map((agent) => ({
        id: agent.id,
        type: "aksaAgent",
        position: { x: agent.position_x, y: agent.position_y },
        data: {
          agent,
          isSelected: selectedAgent?.id === agent.id,
          isActive: activeAgentId === agent.id,
          activeStepLabel: activeAgentId === agent.id ? activeAgentStep : null,
          onSelect: selectAgent,
          onAddChild: addSubAgent,
        },
      })),
    [agents, selectedAgent?.id, activeAgentId, activeAgentStep, selectAgent, addSubAgent]
  );

  const flowEdges: Edge[] = useMemo(
    () =>
      agents
        .filter((a) => a.parent_id !== null)
        .map((a) => {
          const isTargetActive = activeAgentId === a.id;
          return {
            id: `edge_${a.parent_id}_${a.id}`,
            source: a.parent_id as string,
            target: a.id,
            animated: true,
            style: isTargetActive
              ? { stroke: "#10B981", strokeWidth: 3 }
              : { stroke: "#D97757", strokeWidth: 2 },
          };
        }),
    [agents, activeAgentId]
  );

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
    void updateAgentConfig(selectedAgent.id, {
      role_title: tpl.roleTitle,
      description: tpl.description,
      system_prompt: tpl.systemPrompt,
      tool_categories: tpl.capabilities,
      provider: tpl.recommendedProvider,
      model_id: tpl.recommendedModel,
    });
    toast.success(`Template "${tpl.label}" diterapkan pada ${selectedAgent.name}.`);
  };

  const handleApplyAutoRecommendedModel = () => {
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
    void updateAgentConfig(selectedAgent.id, { provider, model_id });
    toast.success(`Model AI direkomendasikan (${model_id}) telah dipilih otomatis.`);
  };

  const handleApplyCustomModel = () => {
    if (!selectedAgent || !customModelId.trim()) return;
    void updateAgentConfig(selectedAgent.id, {
      provider: customProvider,
      model_id: customModelId.trim(),
    });
    setIsCustomMode(false);
    toast.success(`Model Kustom "${customModelId.trim()}" berhasil diterapkan.`);
  };

  const handleAddNewAgent = () => {
    const supervisor = agents.find((a) => a.parent_id === null) ?? agents[0];
    const parent = selectedAgent ?? supervisor;
    if (parent) {
      addSubAgent(parent);
      toast.success(
        "Agen Pendukung baru dibuat dengan izin dasar. Silakan pilih jenis pekerjaan dan kemampuannya."
      );
    }
  };

  const isCurrentModelInPresets = selectedAgent
    ? allPresets.some(
        (p) => p.provider === selectedAgent.provider && p.model_id === selectedAgent.model_id
      )
    : true;

  return (
    <div className="flex-1 flex h-full overflow-hidden bg-[#191918]">
      {/* Safe Agent Deletion Confirmation Dialog (Section 5.4 Keamanan) */}
      <ConfirmDialog
        open={agentPendingDelete !== null}
        title={`Hapus agen "${agentPendingDelete?.name ?? ""}"?`}
        description="Apakah Anda yakin ingin mengeluarkan agen pendukung ini dari Struktur Tim AI Anda?"
        impactNote="Dampak penghapusan: Menghapus agen ini hanya mengeluarkannya dari Struktur Tim AI. File hasil pekerjaan di Ruang Kerja, dokumen di Pengetahuan AKSA, serta memori agen lainnya tetap aman dan tidak akan terhapus."
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

      {/* Left Area: Simple Mode Cards OR Advanced Mode Canvas/Hierarchy */}
      <div className="flex-1 flex flex-col overflow-hidden p-6">
        {/* Top Page Header & Mode Switcher */}
        <div className="flex flex-wrap items-center justify-between gap-4 pb-4 mb-4 border-b border-white/[0.07]">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Network size={20} className="text-[#D97757]" />
              <h1 className="text-[22px] font-semibold tracking-tight text-zinc-100">
                Struktur Tim AI
              </h1>
            </div>
            <p className="text-[13.5px] text-zinc-300">
              Kelola asisten utama dan agen pendukung sesuai jenis pekerjaan yang ingin Anda
              selesaikan.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            <button
              type="button"
              onClick={handleAddNewAgent}
              className="flex items-center gap-1.5 rounded-xl bg-[#D97757] hover:bg-[#c96a4b] px-4 py-2 text-[13px] font-semibold text-white transition-colors shadow-sm"
            >
              <Plus size={15} /> Tambah Agen Pendukung
            </button>

            {/* Simple Mode (Default) vs Advanced Mode Switcher */}
            <div className="flex items-center rounded-xl bg-[#21211F] border border-white/[0.09] p-1">
              <button
                type="button"
                onClick={() => setExperienceMode("sederhana")}
                className={cn(
                  "rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors",
                  experienceMode === "sederhana"
                    ? "bg-[#262624] text-zinc-100 shadow-sm"
                    : "text-zinc-400 hover:text-zinc-200"
                )}
              >
                Mode Sederhana
              </button>
              <button
                type="button"
                onClick={() => setExperienceMode("lanjutan")}
                className={cn(
                  "rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors",
                  experienceMode === "lanjutan"
                    ? "bg-[#262624] text-zinc-100 shadow-sm"
                    : "text-zinc-400 hover:text-zinc-200"
                )}
              >
                Mode Lanjutan
              </button>
            </div>

            {experienceMode === "lanjutan" && (
              <div className="flex items-center rounded-xl bg-[#21211F] border border-white/[0.09] p-1">
                <button
                  type="button"
                  onClick={() => setViewMode("canvas")}
                  className={cn(
                    "flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors",
                    viewMode === "canvas"
                      ? "bg-[#262624] text-zinc-100 shadow-sm"
                      : "text-zinc-400 hover:text-zinc-200"
                  )}
                >
                  <Network size={13} /> Kanvas Visual
                </button>
                <button
                  type="button"
                  onClick={() => setViewMode("list")}
                  className={cn(
                    "flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors",
                    viewMode === "list"
                      ? "bg-[#262624] text-zinc-100 shadow-sm"
                      : "text-zinc-400 hover:text-zinc-200"
                  )}
                >
                  <ListTree size={13} /> Daftar Struktur
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Content Body: Simple Mode vs Advanced Mode */}
        {agents.length === 0 ? (
          <EmptyStateCard
            icon={<Network size={22} />}
            title="Belum ada agent."
            description="Anda belum membuat agent. Buat agent pertama untuk membantu pekerjaan tertentu."
            actionLabel="Tambah Agen Pendukung"
            onAction={handleAddNewAgent}
          />
        ) : experienceMode === "sederhana" ? (
          <div className="flex-1 overflow-y-auto space-y-4 pr-1">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {agents.map((agt) => {
                const badge = getProviderBadgeStyle(agt.provider);
                const isSelected = selectedAgent?.id === agt.id;
                const isActive = activeAgentId === agt.id;
                const isSupervisor = agt.parent_id === null;

                return (
                  <div
                    key={agt.id}
                    onClick={() => selectAgent(agt.id)}
                    className={cn(
                      "rounded-2xl p-5 border cursor-pointer transition-all flex flex-col justify-between space-y-4",
                      isActive
                        ? "bg-[#212921] border-emerald-500 ring-2 ring-emerald-500/30"
                        : isSelected
                        ? "bg-[#262624] border-[#D97757] ring-1 ring-[#D97757]/30"
                        : "bg-[#21211F] border-white/[0.08] hover:border-white/[0.2]"
                    )}
                  >
                    <div className="space-y-2.5">
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-[16px] font-semibold text-zinc-100">
                              {agt.name}
                            </span>
                            <StatusBadge
                              tone={isSupervisor ? "accent" : "neutral"}
                              label={isSupervisor ? "Koordinator Utama" : "Agen Pendukung"}
                            />
                          </div>
                          <p className="text-[13px] font-medium text-zinc-300 mt-0.5">
                            {agt.role_title}
                          </p>
                        </div>

                        {!isSupervisor && (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              setAgentPendingDelete(agt);
                            }}
                            aria-label={`Hapus ${agt.name}`}
                            title="Hapus Agen Pendukung"
                            className="rounded-lg p-1.5 text-zinc-400 hover:text-rose-300 hover:bg-rose-500/15 transition-colors"
                          >
                            <Trash2 size={15} />
                          </button>
                        )}
                      </div>

                      <p className="text-[13px] text-zinc-300 leading-relaxed">
                        {agt.description}
                      </p>
                    </div>

                    {/* Active Capabilities & Explicit Permission Summary */}
                    <div className="space-y-2.5 pt-3 border-t border-white/[0.07]">
                      <div className="flex items-center justify-between text-xs text-zinc-400">
                        <span>Kemampuan &amp; Hak Akses Agen ({agt.tool_categories.length}):</span>
                        <span className="inline-flex items-center gap-1 text-zinc-300">
                          <ProviderIcon provider={agt.provider} size={11} />
                          <span>
                            {badge.label} • {agt.model_id}
                          </span>
                        </span>
                      </div>

                      <div className="flex flex-wrap gap-1.5">
                        {agt.tool_categories.map((cat) => (
                          <span
                            key={cat}
                            className="inline-flex items-center gap-1.5 rounded-lg bg-white/[0.05] border border-white/[0.08] px-2.5 py-1 text-xs text-zinc-200"
                          >
                            <ToolCategoryIcon category={cat} size={12} />
                            <span>{TOOL_CATEGORY_LABELS[cat] ?? cat}</span>
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ) : viewMode === "canvas" ? (
          <div className="flex-1 rounded-2xl bg-[#141413] border border-white/[0.08] overflow-hidden relative">
            <ReactFlow
              nodes={flowNodes}
              edges={flowEdges}
              nodeTypes={nodeTypes}
              fitView
              onNodeDragStop={(_evt, node) => {
                void updateAgentConfig(node.id, {
                  position_x: Math.round(node.position.x),
                  position_y: Math.round(node.position.y),
                });
              }}
              proOptions={{ hideAttribution: true }}
            >
              <Background color="rgba(255,255,255,0.06)" gap={22} />
              <Controls className="!bg-[#21211F] !border !border-white/[0.1] !rounded-xl !shadow-2xl overflow-hidden [&>button]:!bg-[#21211F] [&>button]:!border-b [&>button]:!border-white/[0.08] [&>button]:!fill-zinc-300 [&>button_svg]:!fill-zinc-300" />
            </ReactFlow>
          </div>
        ) : (
          <div className="flex-1 rounded-2xl bg-[#141413] border border-white/[0.08] p-5 overflow-y-auto space-y-3">
            {agents.map((agt) => {
              const badge = getProviderBadgeStyle(agt.provider);
              const isSelected = selectedAgent?.id === agt.id;
              const isActive = activeAgentId === agt.id;
              return (
                <div
                  key={agt.id}
                  onClick={() => selectAgent(agt.id)}
                  className={cn(
                    "flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-2xl p-4 border cursor-pointer transition-colors",
                    isActive
                      ? "bg-[#212921] border-emerald-500"
                      : isSelected
                      ? "bg-[#262624] border-[#D97757]"
                      : "bg-[#21211F] border-white/[0.07] hover:border-white/[0.18]"
                  )}
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="rounded bg-white/[0.08] px-2 py-0.5 text-xs font-semibold text-zinc-200">
                        Tingkat Agen {agt.tier_level + 1}
                      </span>
                      <span className="text-[15px] font-semibold text-zinc-100">{agt.name}</span>
                      <span className="text-[13px] text-zinc-300">— {agt.role_title}</span>
                    </div>
                    <p className="text-[13px] text-zinc-300">{agt.description}</p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span
                      className={cn(
                        "inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-medium border",
                        badge.badgeClass
                      )}
                    >
                      <ProviderIcon provider={agt.provider} size={12} />
                      <span>
                        {badge.label} • {agt.model_id}
                      </span>
                    </span>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        addSubAgent(agt);
                      }}
                      className="rounded-lg bg-white/[0.06] hover:bg-[#D97757]/20 hover:text-[#D97757] border border-white/[0.08] px-2.5 py-1.5 text-xs font-medium text-zinc-200 transition-colors"
                    >
                      + Tambah Agen Pendukung
                    </button>
                    {agt.parent_id !== null && (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setAgentPendingDelete(agt);
                        }}
                        className="rounded-lg p-1.5 text-rose-400 hover:bg-rose-500/15 transition-colors"
                        title="Hapus Agen"
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

      {/* Right Inspector Panel: Guided Simple Configuration + Advanced Section */}
      {selectedAgent && (
        <div className="w-[390px] border-l border-white/[0.08] bg-[#1d1d1b] p-5 overflow-y-auto space-y-5 shrink-0">
          <div className="flex items-center justify-between pb-3 border-b border-white/[0.07]">
            <div className="flex items-center gap-2">
              <SlidersHorizontal size={17} className="text-[#D97757]" />
              <div>
                <h2 className="text-[14px] font-semibold text-zinc-100">
                  Pengaturan Agen Terpilih
                </h2>
                <p className="text-xs text-zinc-400">
                  Tingkat Agen {selectedAgent.tier_level + 1} •{" "}
                  {selectedAgent.parent_id === null ? "Koordinator Utama" : "Agen Pendukung"}
                </p>
              </div>
            </div>

            <button
              type="button"
              onClick={() => addSubAgent(selectedAgent)}
              className="flex items-center gap-1 rounded-xl bg-[#D97757]/15 hover:bg-[#D97757]/25 text-[#F09373] border border-[#D97757]/30 px-2.5 py-1.5 text-xs font-semibold transition-colors"
            >
              <Plus size={13} /> Agen Pendukung
            </button>
          </div>

          {/* Step 1 & 2: Jenis Pekerjaan Template & Nama Agen */}
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-semibold text-zinc-200 mb-1.5">
                1. Pilih Jenis Pekerjaan (Template Cepat)
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
                className="block text-xs font-semibold text-zinc-200 mb-1"
              >
                2. Nama Agen
              </label>
              <input
                id="aksa-agent-name-input"
                type="text"
                value={selectedAgent.name}
                onChange={(e) =>
                  void updateAgentConfig(selectedAgent.id, { name: e.target.value })
                }
                className="w-full rounded-xl bg-[#262624] border border-white/[0.09] px-3 py-2 text-[13px] text-zinc-100 focus:outline-none focus:border-[#D97757]"
              />
            </div>

            <div>
              <label
                htmlFor="aksa-agent-role-input"
                className="block text-xs font-semibold text-zinc-200 mb-1"
              >
                3. Peran / Jabatan di Tim
              </label>
              <input
                id="aksa-agent-role-input"
                type="text"
                value={selectedAgent.role_title}
                onChange={(e) =>
                  void updateAgentConfig(selectedAgent.id, { role_title: e.target.value })
                }
                className="w-full rounded-xl bg-[#262624] border border-white/[0.09] px-3 py-2 text-[13px] text-zinc-100 focus:outline-none focus:border-[#D97757]"
              />
            </div>

            <div>
              <label
                htmlFor="aksa-agent-desc-input"
                className="block text-xs font-semibold text-zinc-200 mb-1"
              >
                4. Deskripsi Tugas
              </label>
              <textarea
                id="aksa-agent-desc-input"
                rows={2}
                value={selectedAgent.description}
                onChange={(e) =>
                  void updateAgentConfig(selectedAgent.id, { description: e.target.value })
                }
                className="w-full rounded-xl bg-[#262624] border border-white/[0.09] p-3 text-[13px] text-zinc-200 leading-relaxed focus:outline-none focus:border-[#D97757]"
              />
            </div>
          </div>

          {/* Step 5: Kemampuan Agen & Hak Akses */}
          <div className="space-y-2.5">
            <div className="flex items-center justify-between">
              <label className="block text-xs font-semibold text-zinc-200">
                5. Kemampuan Agen &amp; Hak Akses
              </label>
              <span className="text-xs text-zinc-400">
                {selectedAgent.tool_categories.length} kemampuan aktif
              </span>
            </div>

            <p className="text-xs text-zinc-400 leading-relaxed flex items-center gap-1.5">
              <ShieldCheck size={13} className="text-emerald-400 shrink-0" />
              <span>Agen hanya dapat menggunakan kemampuan yang dicentang di bawah ini.</span>
            </p>

            {/* Sub-tabs for Core Capabilities, Apps, and Skills */}
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
                Kemampuan ({Object.keys(TOOL_CATEGORY_LABELS).length})
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
              <div className="space-y-1.5 pt-1 max-h-60 overflow-y-auto pr-1">
                {Object.entries(TOOL_CATEGORY_LABELS).map(([key, label]) => {
                  const checked = selectedAgent.tool_categories.includes(key);
                  return (
                    <button
                      key={key}
                      type="button"
                      onClick={() => toggleToolCategory(key)}
                      className={cn(
                        "w-full flex items-start justify-between gap-2 rounded-xl px-3 py-2.5 text-xs border transition-colors text-left",
                        checked
                          ? "bg-white/[0.07] border-[#D97757]/50 text-zinc-100"
                          : "bg-[#262624] border-white/[0.06] text-zinc-300 hover:text-white"
                      )}
                    >
                      <div className="space-y-0.5">
                        <div className="inline-flex items-center gap-2 font-semibold">
                          <ToolCategoryIcon category={key} size={14} />
                          <span>{label}</span>
                        </div>
                        <p className="text-[11.5px] text-zinc-400 pl-5">
                          {TOOL_CATEGORY_DESCRIPTIONS[key]}
                        </p>
                      </div>
                      {checked && <Check size={15} className="text-[#D97757] shrink-0 mt-0.5" />}
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
                          <div className="min-w-0">
                            <span className="block font-medium truncate text-white">
                              {app.display_name}
                            </span>
                            <span className="block text-[11px] text-zinc-400 truncate">
                              {app.category_label || "Aplikasi Komputer"}
                            </span>
                          </div>
                        </div>
                        {checked && <Check size={14} className="text-[#D97757] shrink-0 ml-2" />}
                      </button>
                    );
                  })
                ) : (
                  <div className="p-3.5 rounded-xl bg-[#262624] border border-white/[0.06] text-center space-y-1.5">
                    <ShieldAlert className="w-4 h-4 text-amber-400 mx-auto" />
                    <p className="text-xs font-medium text-zinc-200">
                      Belum Ada Aplikasi yang Diizinkan
                    </p>
                    <p className="text-xs text-zinc-400 leading-relaxed">
                      Hubungkan aplikasi komputer Anda di menu <strong>Aplikasi</strong> agar agen
                      ini dapat menggunakannya.
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
                          <div className="min-w-0">
                            <span className="block font-medium truncate text-white">
                              {skill.display_name}
                            </span>
                            <span className="block text-[11px] text-zinc-400 truncate">
                              v{skill.installed_version} • {skill.publisher}
                            </span>
                          </div>
                        </div>
                        {checked && <Check size={14} className="text-[#D97757] shrink-0 ml-2" />}
                      </button>
                    );
                  })
                ) : (
                  <div className="p-3.5 rounded-xl bg-[#262624] border border-white/[0.06] text-center space-y-1.5">
                    <Sparkles className="w-4 h-4 text-[#D97757] mx-auto" />
                    <p className="text-xs font-medium text-zinc-200">
                      Belum Ada Keahlian Terpasang
                    </p>
                    <p className="text-xs text-zinc-400 leading-relaxed">
                      Kunjungi menu <strong>Keahlian</strong> untuk menambahkan kemampuan baru.
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Step 6: Rekomendasi Model AI Otomatis & Konfigurasi Model Lanjutan */}
          <div className="rounded-xl bg-[#262624] border border-white/[0.08] p-3.5 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-zinc-100">6. Model AI Agen Ini</span>
              <button
                type="button"
                onClick={handleApplyAutoRecommendedModel}
                className="inline-flex items-center gap-1 text-xs font-medium text-[#F09373] hover:underline"
              >
                <Wand2 size={12} />
                <span>Rekomendasi Otomatis</span>
              </button>
            </div>

            <div className="text-xs text-zinc-300 flex items-center justify-between rounded-lg bg-[#191918] border border-white/[0.06] px-3 py-2">
              <span>Model aktif saat ini:</span>
              <span className="font-mono font-semibold text-zinc-100">
                {selectedAgent.provider} / {selectedAgent.model_id}
              </span>
            </div>

            {experienceMode === "lanjutan" && (
              <div className="space-y-3 pt-2 border-t border-white/[0.07]">
                <div className="flex items-center justify-between">
                  <label className="block text-xs font-medium text-zinc-300">
                    Pilih Model AI atau Model Kustom
                  </label>
                  <button
                    type="button"
                    onClick={() => {
                      setIsCustomMode(!isCustomMode);
                      if (!isCustomMode) {
                        setCustomProvider(selectedAgent.provider);
                        setCustomModelId(selectedAgent.model_id);
                      }
                    }}
                    className="text-xs text-[#D97757] hover:underline flex items-center gap-1"
                  >
                    <Edit3 size={11} />
                    <span>{isCustomMode ? "Pilih dari Daftar" : "Model Kustom"}</span>
                  </button>
                </div>

                {!isCustomMode && isCurrentModelInPresets ? (
                  <select
                    aria-label="Pilih Model AI"
                    value={`${selectedAgent.provider}::${selectedAgent.model_id}`}
                    onChange={(e) => {
                      if (e.target.value === "custom_entry") {
                        setIsCustomMode(true);
                        setCustomProvider(selectedAgent.provider);
                        setCustomModelId(selectedAgent.model_id);
                        return;
                      }
                      const [provider, model_id] = e.target.value.split("::") as [
                        ModelProvider,
                        string,
                      ];
                      void updateAgentConfig(selectedAgent.id, { provider, model_id });
                    }}
                    className="w-full rounded-xl bg-[#191918] border border-white/[0.09] px-3 py-2 text-xs text-zinc-100 focus:outline-none focus:border-[#D97757]"
                  >
                    {allPresets.map((preset) => (
                      <option
                        key={`${preset.provider}::${preset.model_id}`}
                        value={`${preset.provider}::${preset.model_id}`}
                        className="bg-[#262624] text-zinc-100"
                      >
                        {preset.label}
                      </option>
                    ))}
                    <option
                      value="custom_entry"
                      className="bg-[#262624] text-[#D97757] font-semibold"
                    >
                      + Gunakan Model Kustom...
                    </option>
                  </select>
                ) : (
                  <div className="rounded-xl bg-[#191918] border border-[#D97757]/40 p-3 space-y-2.5">
                    <div className="space-y-1">
                      <label className="text-xs text-zinc-300">Penyedia AI:</label>
                      <select
                        aria-label="Penyedia AI"
                        value={customProvider}
                        onChange={(e) => setCustomProvider(e.target.value as ModelProvider)}
                        className="w-full rounded-lg bg-[#262624] border border-white/[0.08] px-2.5 py-1.5 text-xs text-zinc-100 focus:outline-none"
                      >
                        <option value="gemini">Google Gemini</option>
                        <option value="anthropic">Anthropic Claude</option>
                        <option value="deepseek">DeepSeek</option>
                        <option value="openai">OpenAI</option>
                        <option value="openrouter">OpenRouter</option>
                        <option value="groq">Groq Cloud</option>
                        <option value="ollama">Ollama Lokal</option>
                        <option value="lmstudio">LM Studio Lokal</option>
                      </select>
                    </div>

                    <div className="space-y-1">
                      <label className="text-xs text-zinc-300">Model AI (Model Kustom):</label>
                      <div className="flex gap-1.5">
                        <input
                          type="text"
                          value={customModelId}
                          onChange={(e) => setCustomModelId(e.target.value)}
                          placeholder="misal: gemini-4-carbon, gpt-6.2-astra"
                          className="flex-1 rounded-lg bg-[#262624] border border-white/[0.08] px-2.5 py-1.5 text-xs text-zinc-100 font-mono focus:outline-none"
                        />
                        <button
                          type="button"
                          onClick={handleApplyCustomModel}
                          disabled={!customModelId.trim()}
                          className="rounded-lg bg-[#D97757] hover:bg-[#c96a4b] px-3 py-1.5 text-xs font-semibold text-white transition-colors disabled:opacity-50"
                        >
                          Terapkan
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                {/* Advanced Temperature & System Prompt */}
                <div className="space-y-1.5 pt-2">
                  <div className="flex justify-between text-xs">
                    <span className="text-zinc-300 font-medium">Kreativitas / Temperatur</span>
                    <span className="text-zinc-200 font-mono">{selectedAgent.temperature}</span>
                  </div>
                  <input
                    type="range"
                    min={0}
                    max={1}
                    step={0.1}
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
                  <label className="block text-xs font-medium text-zinc-300 mb-1">
                    Instruksi Khusus Agen (Mode Lanjutan)
                  </label>
                  <textarea
                    rows={3}
                    value={selectedAgent.system_prompt}
                    onChange={(e) =>
                      void updateAgentConfig(selectedAgent.id, { system_prompt: e.target.value })
                    }
                    className="w-full rounded-xl bg-[#191918] border border-white/[0.08] p-2.5 text-xs text-zinc-200 leading-relaxed focus:outline-none focus:border-[#D97757]"
                  />
                </div>
              </div>
            )}
          </div>

          {/* Step 7: Save & Delete Controls */}
          <div className="pt-3 border-t border-white/[0.07] space-y-2.5">
            <button
              type="button"
              onClick={() => {
                void updateAgentConfig(selectedAgent.id, {
                  name: selectedAgent.name,
                  role_title: selectedAgent.role_title,
                  description: selectedAgent.description,
                });
                toast.success(`Pengaturan agen "${selectedAgent.name}" berhasil disimpan.`);
              }}
              className="w-full flex items-center justify-center gap-2 rounded-xl bg-[#D97757] hover:bg-[#c96a4b] py-2.5 text-[13px] font-semibold text-white transition-colors"
            >
              <Save size={14} />
              <span>Simpan Agen</span>
            </button>

            {selectedAgent.parent_id !== null ? (
              <button
                type="button"
                onClick={() => setAgentPendingDelete(selectedAgent)}
                className="w-full flex items-center justify-center gap-1.5 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/30 py-2.5 text-xs font-semibold text-rose-300 transition-colors"
              >
                <Trash2 size={14} />
                <span>Hapus Agen Pendukung Ini</span>
              </button>
            ) : (
              <p className="text-xs text-zinc-400 text-center">
                Koordinator Utama memimpin tim dan tidak dapat dihapus.
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
