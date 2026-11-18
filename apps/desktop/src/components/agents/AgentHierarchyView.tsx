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
  Laptop,
  FileSpreadsheet,
  Globe,
  Code2,
  MessageSquare,
  Wrench,
} from "lucide-react";
import { useAksaStore } from "@/stores/useAksaStore";
import { cn, getProviderBadgeStyle, TOOL_CATEGORY_LABELS } from "@/lib/utils";
import { ProviderIcon, ToolCategoryIcon } from "@/components/ui/DynamicIcon";
import type { AgentNodeConfig, ModelProvider, DesktopApp, SkillItem } from "@/types/aksa";
import { fetchDesktopAppsRemote, fetchSkillsRemote } from "@/services/engineClient";

const BASE_MODEL_PRESETS: { provider: ModelProvider; model_id: string; label: string }[] = [
  // Google Gemini (Seri Gemini 4 & 3.8)
  { provider: "gemini", model_id: "gemini-4-carbon", label: "[Cloud] Google Gemini • Gemini 4 Carbon (Frontier Tertinggi & Manajer)" },
  { provider: "gemini", model_id: "gemini-4-argon", label: "[Cloud] Google Gemini • Gemini 4 Argon (Flagship Multimodal & Agen)" },
  { provider: "gemini", model_id: "gemini-4-hydrogen", label: "[Cloud] Google Gemini • Gemini 4 Hydrogen (Generasi 4 Efisien)" },
  { provider: "gemini", model_id: "gemini-3.8-flash", label: "[Cloud] Google Gemini • Gemini 3.8 Flash (Super Cepat & Responsif)" },
  { provider: "gemini", model_id: "gemini-3.5-flash-lite", label: "[Cloud] Google Gemini • Gemini 3.5 Flash-Lite (Paling Hemat Kuota)" },

  // Anthropic Claude (Seri Claude 5.5 & Fable 5.2)
  { provider: "anthropic", model_id: "claude-fable-5-2", label: "[Cloud] Anthropic • Claude Fable 5.2 (Penalaran Horizon Panjang)" },
  { provider: "anthropic", model_id: "claude-opus-5-5", label: "[Cloud] Anthropic • Claude Opus 5.5 (Flagship Pengetahuan & Kode)" },
  { provider: "anthropic", model_id: "claude-sonnet-5-5", label: "[Cloud] Anthropic • Claude Sonnet 5.5 (Standar Emas Agen & Computer Use)" },
  { provider: "anthropic", model_id: "claude-haiku-5-5", label: "[Cloud] Anthropic • Claude Haiku 5.5 (Kilat, Murah, & Gesit)" },

  // OpenAI (Seri GPT-6.2 & GPT-6)
  { provider: "openai", model_id: "gpt-6.2-astra", label: "[Cloud] OpenAI • GPT-6.2 Astra (Flagship Penalaran & Agen Otonom)" },
  { provider: "openai", model_id: "gpt-6.2-sol", label: "[Cloud] OpenAI • GPT-6.2 Sol (Performa & Efisiensi Seimbang)" },
  { provider: "openai", model_id: "gpt-6.1-sol", label: "[Cloud] OpenAI • GPT-6.1 Sol (Produksi Enterprise Stabil)" },
  { provider: "openai", model_id: "gpt-6-luna", label: "[Cloud] OpenAI • GPT-6 Luna (Cepat & Hemat Biaya)" },

  // DeepSeek (Seri DeepSeek V4 & R1)
  { provider: "deepseek", model_id: "deepseek-v4-pro", label: "[Cloud] DeepSeek • DeepSeek V4 Pro (Flagship MoE Kode & Logika)" },
  { provider: "deepseek", model_id: "deepseek-flash", label: "[Cloud] DeepSeek • DeepSeek V4.1 Flash (Sangat Hemat / Formula Excel)" },
  { provider: "deepseek", model_id: "deepseek-chat", label: "[Cloud] DeepSeek • DeepSeek Chat (Alias V4 Standar)" },
  { provider: "deepseek", model_id: "deepseek-reasoner", label: "[Cloud] DeepSeek • DeepSeek R1 / Reasoner (Penalaran Chain-of-Thought)" },

  // Groq
  { provider: "groq", model_id: "meta-llama/llama-4-maverick-17b-128e-instruct", label: "[Cloud] Groq • Llama 4 Maverick 17B (Flagship LPU Kilat)" },
  { provider: "groq", model_id: "meta-llama/llama-4-scout-17b-16e-instruct", label: "[Cloud] Groq • Llama 4 Scout 17B (Inferensi LPU Ultra-Cepat)" },
  { provider: "groq", model_id: "qwen/qwen3-32b", label: "[Cloud] Groq • Qwen 3.8 / 3 32B (Penalaran & Kode Kilat LPU)" },
  { provider: "groq", model_id: "deepseek-r1-distill-llama-70b", label: "[Cloud] Groq • DeepSeek R1 Distill 70B (Penalaran Kilat)" },

  // OpenRouter
  { provider: "openrouter", model_id: "anthropic/claude-opus-5-5", label: "[Cloud] OpenRouter • Claude Opus 5.5" },
  { provider: "openrouter", model_id: "anthropic/claude-sonnet-5-5", label: "[Cloud] OpenRouter • Claude Sonnet 5.5" },
  { provider: "openrouter", model_id: "google/gemini-4-carbon", label: "[Cloud] OpenRouter • Gemini 4 Carbon" },
  { provider: "openrouter", model_id: "openai/gpt-6.2-astra", label: "[Cloud] OpenRouter • OpenAI GPT-6.2 Astra" },
  { provider: "openrouter", model_id: "deepseek/deepseek-v4-pro", label: "[Cloud] OpenRouter • DeepSeek V4 Pro" },
  { provider: "openrouter", model_id: "openrouter/auto", label: "[Cloud] OpenRouter • Auto Router (Rute Otomatis)" },

  // Ollama (Lokal Gratis)
  { provider: "ollama", model_id: "qwen3.8:8b", label: "[Lokal] Ollama • Qwen 3.8 8B (Rekomendasi Utama Indonesia & Kode)" },
  { provider: "ollama", model_id: "qwen3.8:14b", label: "[Lokal] Ollama • Qwen 3.8 14B (Akurasi Tinggi Lokal)" },
  { provider: "ollama", model_id: "qwen3-coder:30b", label: "[Lokal] Ollama • Qwen 3 Coder 30B (Spesialis Kode)" },
  { provider: "ollama", model_id: "gemma4:12b", label: "[Lokal] Ollama • Google Gemma 4 12B (Multimodal Lokal Gen-4)" },
  { provider: "ollama", model_id: "deepseek-r1:8b", label: "[Lokal] Ollama • DeepSeek R1 8B (Penalaran Offline)" },
  { provider: "ollama", model_id: "llama4:scout", label: "[Lokal] Ollama • Meta Llama 4 Scout (Flagship Lokal)" },

  // LM Studio
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
        "w-[295px] rounded-2xl p-4 cursor-pointer transition-all border text-left space-y-2.5 shadow-xl select-none relative",
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

      {/* Active Pulse Pill */}
      {isActive && (
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 text-[10px] font-semibold">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
          <span className="truncate">{activeStepLabel || "Sedang Bekerja..."}</span>
        </div>
      )}

      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <span className="rounded bg-white/[0.07] px-1.5 py-0.5 text-[10px] font-semibold text-zinc-200">
              Lv.{agent.tier_level + 1}
            </span>
            <span className="text-xs font-semibold text-zinc-100 truncate">{agent.name}</span>
          </div>
          <p className="text-[11px] text-zinc-400 truncate mt-0.5">{agent.role_title}</p>
        </div>

        <button
          onClick={(e) => {
            e.stopPropagation();
            onAddChild(agent);
          }}
          title="Tambah Sub-Agen di bawah posisi ini"
          className="flex items-center gap-1 rounded-lg bg-white/[0.06] hover:bg-[#D97757]/20 hover:text-[#D97757] border border-white/[0.08] px-2 py-1 text-[10px] font-medium text-zinc-200 transition-colors shrink-0"
        >
          <Plus size={11} /> Sub-Agen
        </button>
      </div>

      <div className="flex items-center justify-between rounded-xl bg-black/35 border border-white/[0.06] px-2.5 py-1.5">
        <div className="flex items-center gap-1.5 truncate">
          {badge.isLocal ? (
            <Cpu size={12} className="text-emerald-400 shrink-0" />
          ) : (
            <Cloud size={12} className="text-[#D97757] shrink-0" />
          )}
          <span className="text-[11px] font-medium text-zinc-200 truncate">{agent.model_id}</span>
        </div>
        <span
          className={cn(
            "rounded px-1.5 py-0.5 text-[9px] font-semibold border shrink-0",
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
            className="inline-flex items-center gap-1 rounded-md bg-white/[0.04] border border-white/[0.06] px-1.5 py-0.5 text-[9px] text-zinc-300"
          >
            <ToolCategoryIcon category={cat} size={10} />
            <span>{TOOL_CATEGORY_LABELS[cat] ?? cat}</span>
          </span>
        ))}
        {agent.tool_categories.length > 3 && (
          <span className="rounded-md bg-white/[0.04] px-1.5 py-0.5 text-[9px] text-zinc-400">
            +{agent.tool_categories.length - 3} alat
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

  const [viewMode, setViewMode] = useState<"canvas" | "list">("canvas");
  const [isCustomMode, setIsCustomMode] = useState(false);
  const [customModelId, setCustomModelId] = useState("");
  const [customProvider, setCustomProvider] = useState<ModelProvider>("gemini");
  const [connectedApps, setConnectedApps] = useState<DesktopApp[]>([]);
  const [installedSkills, setInstalledSkills] = useState<SkillItem[]>([]);
  const [toolsTab, setToolsTab] = useState<"apps" | "skills" | "core">("apps");

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

  // Build dynamic presets list including any running Ollama models
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
    } else {
      list.push(
        { provider: "ollama", model_id: "qwen3.8:8b", label: "[Lokal] Ollama • Qwen 3.8 8B (Offline)" },
        { provider: "ollama", model_id: "gemma4:12b", label: "[Lokal] Ollama • Gemma 4 12B (Offline)" }
      );
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

  const handleApplyCustomModel = () => {
    if (!selectedAgent || !customModelId.trim()) return;
    void updateAgentConfig(selectedAgent.id, {
      provider: customProvider,
      model_id: customModelId.trim(),
    });
    setIsCustomMode(false);
  };

  const handleAddNewAgent = () => {
    const parent = selectedAgent ?? agents[0];
    if (parent) {
      addSubAgent(parent);
    }
  };

  const isCurrentModelInPresets = selectedAgent
    ? allPresets.some(
        (p) => p.provider === selectedAgent.provider && p.model_id === selectedAgent.model_id
      )
    : true;

  return (
    <div className="flex-1 flex h-full overflow-hidden bg-[#191918]">
      {/* Left: Visual React Flow Canvas OR Organization List */}
      <div className="flex-1 flex flex-col overflow-hidden p-5">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <div>
            <div className="flex items-center gap-2">
              <Network size={18} className="text-[#D97757]" />
              <h1 className="text-base font-semibold text-zinc-100">
                Perancang Hirarki Tim Agen Bertingkat
              </h1>
            </div>
            <p className="text-xs text-zinc-400 mt-0.5">
              Kelola struktur Manajer Utama &amp; Sub-Agen Spesialis. Dukungan universal untuk model Cloud dan Lokal terbaru.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleAddNewAgent}
              className="flex items-center gap-1.5 rounded-xl bg-[#D97757] hover:bg-[#c96a4b] px-3.5 py-1.5 text-xs font-medium text-white transition-colors shadow-sm"
            >
              <Plus size={14} /> Tambah Sub-Agen
            </button>

            {/* Toggle Canvas vs Simple Organization List */}
            <div className="flex items-center rounded-xl bg-[#21211F] border border-white/[0.08] p-1">
              <button
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
          </div>
        </div>

        {viewMode === "canvas" ? (
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
                    "flex items-center justify-between rounded-2xl p-4 border cursor-pointer transition-colors",
                    isActive
                      ? "bg-[#212921] border-emerald-500 ring-2 ring-emerald-500/40 shadow-[0_0_25px_rgba(16,185,129,0.25)] animate-pulse"
                      : isSelected
                      ? "bg-[#262624] border-[#D97757]"
                      : "bg-[#21211F] border-white/[0.07] hover:border-white/[0.18]"
                  )}
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="rounded bg-white/[0.07] px-2 py-0.5 text-[10px] font-semibold text-zinc-200">
                        Level {agt.tier_level + 1}
                      </span>
                      <span className="text-sm font-semibold text-zinc-100">{agt.name}</span>
                      <span className="text-xs text-zinc-400">— {agt.role_title}</span>
                      {isActive && (
                        <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/20 border border-emerald-500/40 px-2 py-0.5 text-[10.5px] font-semibold text-emerald-300">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
                          <span>Sedang Bekerja...</span>
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-zinc-400">{agt.description}</p>
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
                      onClick={(e) => {
                        e.stopPropagation();
                        addSubAgent(agt);
                      }}
                      className="rounded-lg bg-white/[0.06] hover:bg-[#D97757]/20 hover:text-[#D97757] border border-white/[0.08] px-2.5 py-1 text-xs text-zinc-200 transition-colors"
                    >
                      + Sub-Agen
                    </button>
                    {agt.parent_id !== null && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          if (confirm(`Apakah Anda yakin ingin menghapus agen "${agt.name}" dari tim?`)) {
                            void deleteAgentNode(agt.id);
                          }
                        }}
                        className="rounded-lg p-1.5 text-rose-400 hover:bg-rose-500/15 transition-colors"
                        title="Hapus Agen"
                      >
                        <Trash2 size={14} />
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Right: Slide-Over Agent Configurator & Inspector */}
      {selectedAgent && (
        <div className="w-[360px] border-l border-white/[0.08] bg-[#1d1d1b] p-5 overflow-y-auto space-y-5 shrink-0">
          <div className="flex items-center justify-between pb-3 border-b border-white/[0.06]">
            <div className="flex items-center gap-2">
              <SlidersHorizontal size={16} className="text-[#D97757]" />
              <div>
                <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-200">
                  Konfigurasi Agen &amp; Model
                </h2>
                <p className="text-[11px] text-zinc-400">
                  Level {selectedAgent.tier_level + 1} • {selectedAgent.id}
                </p>
              </div>
            </div>

            <button
              onClick={() => addSubAgent(selectedAgent)}
              title="Tambah sub-agen di bawah agen ini"
              className="flex items-center gap-1 rounded-lg bg-[#D97757]/15 hover:bg-[#D97757]/25 text-[#D97757] border border-[#D97757]/30 px-2 py-1 text-[11px] font-medium transition-colors"
            >
              <Plus size={12} /> Sub-Agen
            </button>
          </div>

          <div className="space-y-3">
            <div>
              <label className="block text-[11px] font-medium text-zinc-300 mb-1">Nama Agen</label>
              <input
                type="text"
                value={selectedAgent.name}
                onChange={(e) =>
                  void updateAgentConfig(selectedAgent.id, { name: e.target.value })
                }
                className="w-full rounded-xl bg-[#262624] border border-white/[0.08] px-3 py-2 text-xs text-zinc-100 focus:outline-none focus:border-[#D97757]"
              />
            </div>

            <div>
              <label className="block text-[11px] font-medium text-zinc-300 mb-1">
                Jabatan / Peran di Tim
              </label>
              <input
                type="text"
                value={selectedAgent.role_title}
                onChange={(e) =>
                  void updateAgentConfig(selectedAgent.id, { role_title: e.target.value })
                }
                className="w-full rounded-xl bg-[#262624] border border-white/[0.08] px-3 py-2 text-xs text-zinc-100 focus:outline-none focus:border-[#D97757]"
              />
            </div>
          </div>

          {/* Model Selection with Universal Custom Model Support */}
          <div className="space-y-2.5">
            <div className="flex items-center justify-between">
              <label className="block text-[11px] font-medium text-zinc-300">
                Pilih Model AI Khusus Agen Ini
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
                className="text-[11px] text-[#D97757] hover:underline flex items-center gap-1"
              >
                <Edit3 size={11} />
                <span>{isCustomMode ? "Pilih dari Daftar" : "Tulis Model Kustom"}</span>
              </button>
            </div>

            {!isCustomMode && isCurrentModelInPresets ? (
              <select
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
                className="w-full rounded-xl bg-[#262624] border border-white/[0.08] px-3 py-2.5 text-xs text-zinc-100 focus:outline-none focus:border-[#D97757]"
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
                <option value="custom_entry" className="bg-[#262624] text-[#D97757] font-semibold">
                  + Tulis Model Kustom / Model Terbaru Sendiri...
                </option>
              </select>
            ) : (
              /* Custom Model ID Entry Mode (Supports Any Newly Released Model Instantly) */
              <div className="rounded-xl bg-[#262624] border border-[#D97757]/40 p-3 space-y-2.5">
                <div className="flex items-center justify-between text-[11px] text-zinc-300 font-medium">
                  <span>Input Model Baru / Kustom:</span>
                  <span className="text-[10px] text-emerald-400 font-mono">Dukungan Universal</span>
                </div>

                <div className="space-y-1">
                  <label className="text-[10px] text-zinc-400">Penyedia AI (Provider):</label>
                  <select
                    value={customProvider}
                    onChange={(e) => setCustomProvider(e.target.value as ModelProvider)}
                    className="w-full rounded-lg bg-[#1f1f1d] border border-white/[0.08] px-2.5 py-1.5 text-xs text-zinc-100 focus:outline-none"
                  >
                    <option value="gemini">Google Gemini</option>
                    <option value="anthropic">Anthropic Claude</option>
                    <option value="deepseek">DeepSeek</option>
                    <option value="openai">OpenAI</option>
                    <option value="openrouter">OpenRouter (Ratusan Model)</option>
                    <option value="groq">Groq Cloud</option>
                    <option value="ollama">Ollama Lokal</option>
                    <option value="lmstudio">LM Studio Lokal</option>
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="text-[10px] text-zinc-400">String ID Model Baru:</label>
                  <div className="flex gap-1.5">
                    <input
                      type="text"
                      value={customModelId}
                      onChange={(e) => setCustomModelId(e.target.value)}
                      placeholder="misal: gemini-4-carbon, gpt-6.2-astra, claude-opus-5-5"
                      className="flex-1 rounded-lg bg-[#1f1f1d] border border-white/[0.08] px-2.5 py-1.5 text-xs text-zinc-100 placeholder:text-zinc-600 focus:outline-none font-mono"
                    />
                    <button
                      type="button"
                      onClick={handleApplyCustomModel}
                      disabled={!customModelId.trim()}
                      className="rounded-lg bg-[#D97757] hover:bg-[#c96a4b] px-3 py-1.5 text-xs font-medium text-white transition-colors disabled:opacity-50"
                    >
                      Terapkan
                    </button>
                  </div>
                </div>

                <p className="text-[10.5px] text-zinc-400 leading-relaxed">
                  Backend AKSA menggunakan arsitektur LiteLLM sehingga otomatis mendukung nama model baru apa pun yang dirilis tanpa menunggu pembaruan software.
                </p>
              </div>
            )}

            {selectedAgent.provider === "ollama" && !engineHealth.ollama_online ? (
              <p className="text-[10.5px] text-amber-400 flex items-center gap-1">
                <Sparkles size={11} className="text-amber-400 shrink-0" />
                Ollama belum aktif di komputer Anda. Jalankan `ollama run qwen3.8:8b` atau pilih model Cloud API di atas.
              </p>
            ) : (
              <p className="text-[10.5px] text-zinc-400 flex items-center gap-1">
                <Sparkles size={11} className="text-emerald-400 shrink-0" />
                {engineHealth.ollama_online
                  ? "Ollama aktif di port 11434 • 100% gratis & hemat token."
                  : "Model Cloud API menggunakan kuota API Key tersimpan Anda."}
              </p>
            )}
          </div>

          {/* Temperature Slider */}
          <div className="space-y-1.5">
            <div className="flex justify-between text-[11px]">
              <span className="text-zinc-300 font-medium">Temperatur Penalaran</span>
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

          {/* Bahasa Indonesia System Prompt */}
          <div>
            <label className="block text-[11px] font-medium text-zinc-300 mb-1">
              Instruksi &amp; Karakter Agen (Bahasa Indonesia)
            </label>
            <textarea
              rows={4}
              value={selectedAgent.system_prompt}
              onChange={(e) =>
                void updateAgentConfig(selectedAgent.id, { system_prompt: e.target.value })
              }
              className="w-full rounded-xl bg-[#262624] border border-white/[0.08] p-3 text-xs text-zinc-200 leading-relaxed focus:outline-none focus:border-[#D97757]"
            />
          </div>

          {/* Lazy Tool Categories Assignment */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="block text-[11px] font-medium text-zinc-300">
                Keahlian &amp; Akses Alat (Lazy Tool Loading)
              </label>
              <span className="text-[10px] text-zinc-500 font-mono">
                {selectedAgent.tool_categories.length} izin aktif
              </span>
            </div>

            {/* Sub-tabs for Apps, Skills, and Core Tools */}
            <div className="flex items-center gap-1 p-1 rounded-lg bg-[#262624] border border-white/[0.06]">
              <button
                type="button"
                onClick={() => setToolsTab("apps")}
                className={cn(
                  "flex-1 py-1 px-1.5 rounded-md text-[10px] font-medium transition-colors text-center truncate",
                  toolsTab === "apps"
                    ? "bg-[#D97757] text-white shadow-sm"
                    : "text-zinc-400 hover:text-zinc-200"
                )}
              >
                Aplikasi ({connectedApps.length})
              </button>
              <button
                type="button"
                onClick={() => setToolsTab("skills")}
                className={cn(
                  "flex-1 py-1 px-1.5 rounded-md text-[10px] font-medium transition-colors text-center truncate",
                  toolsTab === "skills"
                    ? "bg-[#D97757] text-white shadow-sm"
                    : "text-zinc-400 hover:text-zinc-200"
                )}
              >
                Keahlian ({installedSkills.length})
              </button>
              <button
                type="button"
                onClick={() => setToolsTab("core")}
                className={cn(
                  "flex-1 py-1 px-1.5 rounded-md text-[10px] font-medium transition-colors text-center truncate",
                  toolsTab === "core"
                    ? "bg-[#D97757] text-white shadow-sm"
                    : "text-zinc-400 hover:text-zinc-200"
                )}
              >
                Alat Inti ({Object.keys(TOOL_CATEGORY_LABELS).length})
              </button>
            </div>

            {/* Tab Content 1: Connected Applications */}
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
                            ? "bg-white/[0.06] border-[#D97757]/40 text-zinc-200"
                            : "bg-[#262624] border-white/[0.06] text-zinc-400 hover:text-zinc-200"
                        )}
                      >
                        <div className="inline-flex items-center gap-2 min-w-0">
                          {getAppCategoryIcon(app.category_label)}
                          <div className="min-w-0">
                            <span className="block font-medium truncate text-white">{app.display_name}</span>
                            <span className="block text-[10px] text-zinc-500 truncate">{app.category_label || "Aplikasi PC"}</span>
                          </div>
                        </div>
                        {checked && <Check size={14} className="text-[#D97757] shrink-0 ml-2" />}
                      </button>
                    );
                  })
                ) : (
                  <div className="p-3 rounded-xl bg-[#262624] border border-white/[0.06] text-center space-y-1.5">
                    <ShieldAlert className="w-4 h-4 text-amber-500 mx-auto" />
                    <p className="text-[11px] font-medium text-zinc-300">Belum Ada Aplikasi yang Diizinkan</p>
                    <p className="text-[10px] text-zinc-500 leading-relaxed">
                      Hubungkan software PC Anda (Excel, Chrome, VS Code) di menu <strong>Aplikasi PC</strong> agar agen ini dapat mengaksesnya.
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* Tab Content 2: Installed Agent Skills */}
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
                            ? "bg-white/[0.06] border-[#D97757]/40 text-zinc-200"
                            : "bg-[#262624] border-white/[0.06] text-zinc-400 hover:text-zinc-200"
                        )}
                      >
                        <div className="inline-flex items-center gap-2 min-w-0">
                          <Sparkles size={13} className="text-[#D97757] shrink-0" />
                          <div className="min-w-0">
                            <span className="block font-medium truncate text-white">{skill.display_name}</span>
                            <span className="block text-[10px] text-zinc-500 truncate">v{skill.installed_version} • {skill.publisher}</span>
                          </div>
                        </div>
                        {checked && <Check size={14} className="text-[#D97757] shrink-0 ml-2" />}
                      </button>
                    );
                  })
                ) : (
                  <div className="p-3 rounded-xl bg-[#262624] border border-white/[0.06] text-center space-y-1.5">
                    <Sparkles className="w-4 h-4 text-[#D97757] mx-auto" />
                    <p className="text-[11px] font-medium text-zinc-300">Belum Ada Keahlian Terpasang</p>
                    <p className="text-[10px] text-zinc-500 leading-relaxed">
                      Kunjungi menu <strong>Keahlian</strong> untuk memasang paket keahlian populer (Pemodelan Finansial, Naskah Dinas, Ekstraktor PDF, dll).
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* Tab Content 3: Core System Tools */}
            {toolsTab === "core" && (
              <div className="space-y-1.5 pt-1">
                {Object.entries(TOOL_CATEGORY_LABELS).map(([key, label]) => {
                  const checked = selectedAgent.tool_categories.includes(key);
                  return (
                    <button
                      key={key}
                      type="button"
                      onClick={() => toggleToolCategory(key)}
                      className={cn(
                        "w-full flex items-center justify-between rounded-xl px-3 py-2 text-xs border transition-colors text-left",
                        checked
                          ? "bg-white/[0.06] border-[#D97757]/40 text-zinc-200"
                          : "bg-[#262624] border-white/[0.06] text-zinc-400 hover:text-zinc-200"
                      )}
                    >
                      <span className="inline-flex items-center gap-2">
                        <ToolCategoryIcon category={key} size={13} />
                        <span>{label}</span>
                      </span>
                      {checked && <Check size={14} className="text-[#D97757]" />}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Delete Agent Section */}
          <div className="pt-4 border-t border-white/[0.06]">
            {selectedAgent.parent_id !== null ? (
              <button
                type="button"
                onClick={() => {
                  if (confirm(`Apakah Anda yakin ingin menghapus agen "${selectedAgent.name}" dari tim?`)) {
                    void deleteAgentNode(selectedAgent.id);
                  }
                }}
                className="w-full flex items-center justify-center gap-1.5 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/30 py-2.5 text-xs font-medium text-rose-300 transition-colors"
              >
                <Trash2 size={13} />
                <span>Hapus Sub-Agen Ini dari Tim</span>
              </button>
            ) : (
              <p className="text-[11px] text-zinc-500 text-center">
                Manajer Eksekutif adalah pimpinan tim utama dan tidak dapat dihapus.
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
