import React, { useState, useEffect } from "react";
import {
  Settings,
  FolderOpen,
  FolderPlus,
  FolderLock,
  Cpu,
  KeyRound,
  Zap,
  RefreshCw,
  Copy,
  Check,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
  Shield,
  ShieldCheck,
  OctagonAlert,
  Sliders,
  Plus,
  Trash2,
  Play,
  Layers,
  Sparkles,
  Info,
  Eye,
  EyeOff,
} from "lucide-react";
import { useAksaStore } from "@/stores/useAksaStore";
import {
  saveProviderApiKey,
  fetchConfiguredProviders,
  fetchProviderDetails,
  testModelConnectionRemote,
} from "@/services/engineClient";
import { formatNumberID } from "@/lib/utils";
import { ProviderIcon } from "@/components/ui/DynamicIcon";
import type { ModelProvider } from "@/types/aksa";
import { KnowledgeBaseView } from "@/components/rag/KnowledgeBaseView";
import { TelegramGatewayView } from "@/components/telegram/TelegramGatewayView";
import { ApplicationsView } from "@/components/apps/ApplicationsView";
import { SkillsView } from "@/components/skills/SkillsView";
import { PermissionsAndPCView } from "@/components/settings/PermissionsAndPCView";

interface PreloadedModel {
  provider: ModelProvider;
  model_id: string;
  name: string;
  badge_label: string;
  description: string;
  is_recommended?: boolean;
}

const PRELOADED_MODELS: PreloadedModel[] = [
  // Google Gemini (Seri Gemini 4 & 3.8)
  {
    provider: "gemini",
    model_id: "gemini-4-carbon",
    name: "Gemini 4 Carbon",
    badge_label: "Frontier Tertinggi & Manajer",
    description: "Model frontier kasta tertinggi Google Gemini 4 untuk penalaran mendalam, koordinasi tim multi-agen, dan arsitektur strategis.",
    is_recommended: true,
  },
  {
    provider: "gemini",
    model_id: "gemini-4-argon",
    name: "Gemini 4 Argon",
    badge_label: "Flagship Multimodal & Agen",
    description: "Model unggulan Gemini 4 untuk pemrosesan multimodal presisi tinggi, eksekusi tool-calling kompleks, dan dokumen panjang.",
    is_recommended: true,
  },
  {
    provider: "gemini",
    model_id: "gemini-4-hydrogen",
    name: "Gemini 4 Hydrogen",
    badge_label: "Generasi 4 Efisien",
    description: "Varian berkecepatan tinggi di keluarga Gemini 4 dengan keseimbangan optimal antara kecerdasan dan latensi rendah.",
  },
  {
    provider: "gemini",
    model_id: "gemini-3.8-flash",
    name: "Gemini 3.8 Flash",
    badge_label: "Super Cepat & Tangkas",
    description: "Model harian andalan berkecepatan ekstra tinggi untuk beban kerja agen responsif dan automasi real-time.",
    is_recommended: true,
  },
  {
    provider: "gemini",
    model_id: "gemini-3.5-flash-lite",
    name: "Gemini 3.5 Flash-Lite",
    badge_label: "Paling Hemat Kuota",
    description: "Versi ultra-ringan dengan efisiensi biaya maksimal untuk ekstraksi data massal dan tugas berulang.",
  },

  // Anthropic Claude (Seri Claude 5.5 & Fable 5.2)
  {
    provider: "anthropic",
    model_id: "claude-fable-5-2",
    name: "Claude Fable 5.2",
    badge_label: "Penalaran Horizon Panjang",
    description: "Generasi frontier Anthropic Fable 5.2 untuk riset otonom multi-tahap, penalaran algoritmik berat, dan rekayasa sistem.",
    is_recommended: true,
  },
  {
    provider: "anthropic",
    model_id: "claude-opus-5-5",
    name: "Claude Opus 5.5",
    badge_label: "Flagship Pengetahuan & Kode",
    description: "Model utama Claude 5.5 untuk telaah dokumen hukum/keuangan mendalam, penulisan naskah eksekutif, dan orkestrasi agen.",
    is_recommended: true,
  },
  {
    provider: "anthropic",
    model_id: "claude-sonnet-5-5",
    name: "Claude Sonnet 5.5",
    badge_label: "Standar Emas Agen & Computer Use",
    description: "Kombinasi kecepatan dan kecerdasan terbaik generasi Claude 5.5 untuk pemrograman, Office, dan automasi layar PC.",
    is_recommended: true,
  },
  {
    provider: "anthropic",
    model_id: "claude-haiku-5-5",
    name: "Claude Haiku 5.5",
    badge_label: "Kilat & Berbiaya Rendah",
    description: "Model tercepat di keluarga Claude 5.5 untuk respons instan, klasifikasi dokumen, dan delegasi sub-agen.",
  },

  // OpenAI (Seri GPT-6.2 & GPT-6)
  {
    provider: "openai",
    model_id: "gpt-6.2-astra",
    name: "OpenAI GPT-6.2 Astra",
    badge_label: "Flagship Penalaran & Agen",
    description: "Model frontier tertinggi OpenAI generasi GPT-6.2 untuk penalaran kompleks, eksekusi agen otonom, dan sintesis kode.",
    is_recommended: true,
  },
  {
    provider: "openai",
    model_id: "gpt-6.2-sol",
    name: "OpenAI GPT-6.2 Sol",
    badge_label: "Performa & Efisiensi Seimbang",
    description: "Model serbaguna generasi GPT-6.2 dengan ketajaman instruksi tinggi dan kecepatan optimal untuk produktivitas kantor.",
    is_recommended: true,
  },
  {
    provider: "openai",
    model_id: "gpt-6.1-sol",
    name: "OpenAI GPT-6.1 Sol",
    badge_label: "Produksi Enterprise Stabil",
    description: "Varian stabil seri GPT-6.1 untuk pemrosesan spreadsheet, analisis laporan, dan integrasi JSON schema presisi.",
  },
  {
    provider: "openai",
    model_id: "gpt-6-luna",
    name: "OpenAI GPT-6 Luna",
    badge_label: "Cepat & Hemat Biaya",
    description: "Model ringan generasi GPT-6 yang dirancang untuk tugas berfrekuensi tinggi dengan latensi sangat rendah.",
  },

  // DeepSeek (Seri DeepSeek V4 & R1)
  {
    provider: "deepseek",
    model_id: "deepseek-v4-pro",
    name: "DeepSeek V4 Pro",
    badge_label: "Flagship MoE Kode & Logika",
    description: "Arsitektur Mixture-of-Experts generasi V4 terbaru untuk rekayasa kode, pemodelan finansial Excel, dan analisis data.",
    is_recommended: true,
  },
  {
    provider: "deepseek",
    model_id: "deepseek-flash",
    name: "DeepSeek V4.1 Flash",
    badge_label: "Sangat Hemat Token & Cepat",
    description: "Model multimodal konteks panjang V4.1 Flash yang super hemat biaya untuk pembuatan rumus Excel, Word, dan PPT.",
    is_recommended: true,
  },
  {
    provider: "deepseek",
    model_id: "deepseek-chat",
    name: "DeepSeek Chat (V4 Alias)",
    badge_label: "Endpoint Standar V4",
    description: "Alias resmi DeepSeek yang otomatis mengarah ke checkpoint V4 aktif untuk pengolahan dokumen harian.",
  },
  {
    provider: "deepseek",
    model_id: "deepseek-reasoner",
    name: "DeepSeek R1 / Reasoner",
    badge_label: "Penalaran Chain-of-Thought",
    description: "Model penalaran matematis dan verifikasi logika mendalam dengan jejak berpikir langkah-demi-langkah.",
    is_recommended: true,
  },

  // Groq
  {
    provider: "groq",
    model_id: "meta-llama/llama-4-maverick-17b-128e-instruct",
    name: "Llama 4 Maverick 17B (Groq)",
    badge_label: "Flagship Llama 4 LPU",
    description: "Model multimodal MoE generasi Llama 4 (128 experts) dengan akselerasi perangkat keras LPU Groq super cepat.",
    is_recommended: true,
  },
  {
    provider: "groq",
    model_id: "meta-llama/llama-4-scout-17b-16e-instruct",
    name: "Llama 4 Scout 17B (Groq)",
    badge_label: "Inferensi LPU Kilat",
    description: "Model Llama 4 Scout berkecepatan ratusan token/detik untuk peringkasan dokumen dan eksekusi alat instan.",
  },
  {
    provider: "groq",
    model_id: "qwen/qwen3-32b",
    name: "Qwen 3.8 / 3 32B (Groq)",
    badge_label: "Penalaran & Kode LPU",
    description: "Model penalaran hibrida dan pemrograman tingkat lanjut yang berjalan di atas chip LPU Groq.",
    is_recommended: true,
  },
  {
    provider: "groq",
    model_id: "deepseek-r1-distill-llama-70b",
    name: "DeepSeek R1 Distill 70B (Groq)",
    badge_label: "Penalaran Kilat Groq",
    description: "Kemampuan penalaran mendalam DeepSeek R1 dengan kecepatan inferensi LPU ultra-rendah latensi.",
  },

  // OpenRouter
  {
    provider: "openrouter",
    model_id: "anthropic/claude-opus-5-5",
    name: "Claude Opus 5.5 (OpenRouter)",
    badge_label: "Router Claude 5.5",
    description: "Akses langsung ke flagship Anthropic Claude Opus 5.5 melalui gerbang terpadu OpenRouter.",
    is_recommended: true,
  },
  {
    provider: "openrouter",
    model_id: "anthropic/claude-sonnet-5-5",
    name: "Claude Sonnet 5.5 (OpenRouter)",
    badge_label: "Router Sonnet 5.5",
    description: "Model agen dan kode Claude Sonnet 5.5 via satu kunci API OpenRouter.",
    is_recommended: true,
  },
  {
    provider: "openrouter",
    model_id: "google/gemini-4-carbon",
    name: "Gemini 4 Carbon (OpenRouter)",
    badge_label: "Router Gemini 4",
    description: "Model frontier Google Gemini 4 Carbon melalui agregator OpenRouter.",
  },
  {
    provider: "openrouter",
    model_id: "openai/gpt-6.2-astra",
    name: "OpenAI GPT-6.2 Astra (OpenRouter)",
    badge_label: "Router GPT-6.2",
    description: "Akses model flagship OpenAI GPT-6.2 Astra melalui infrastruktur OpenRouter.",
  },
  {
    provider: "openrouter",
    model_id: "deepseek/deepseek-v4-pro",
    name: "DeepSeek V4 Pro (OpenRouter)",
    badge_label: "Router DeepSeek V4",
    description: "Model MoE DeepSeek V4 Pro via jaringan global OpenRouter.",
  },
  {
    provider: "openrouter",
    model_id: "openrouter/auto",
    name: "OpenRouter Auto Gateway",
    badge_label: "Router Cerdas Otomatis",
    description: "Gerbang terpadu yang merutekan secara dinamis ke model terbaik berdasarkan kompleksitas prompt.",
    is_recommended: true,
  },

  // Ollama (Lokal Gratis)
  {
    provider: "ollama",
    model_id: "qwen3.8:8b",
    name: "Qwen 3.8 8B (Ollama)",
    badge_label: "Rekomendasi Lokal Utama",
    description: "Model lokal generasi Qwen 3.8 terbaru untuk Bahasa Indonesia, penalaran hibrida, tool-calling, dan privasi offline 100%.",
    is_recommended: true,
  },
  {
    provider: "ollama",
    model_id: "qwen3.8:14b",
    name: "Qwen 3.8 14B (Ollama)",
    badge_label: "Akurasi Tinggi Lokal",
    description: "Varian 14B Qwen 3.8 dengan ketajaman analisis dokumen RAG dan sintesis laporan setara model cloud.",
  },
  {
    provider: "ollama",
    model_id: "qwen3-coder:30b",
    name: "Qwen 3 Coder 30B (Ollama)",
    badge_label: "Spesialis Kode Lokal",
    description: "Model coding lokal untuk penulisan skrip Python otomatis, analisis CSV/Excel, dan debugging.",
  },
  {
    provider: "ollama",
    model_id: "gemma4:12b",
    name: "Google Gemma 4 12B (Ollama)",
    badge_label: "Multimodal Lokal Gen-4",
    description: "Model open-weights generasi ke-4 dari Google dengan dukungan teks dan vision berkapasitas konteks besar.",
    is_recommended: true,
  },
  {
    provider: "ollama",
    model_id: "deepseek-r1:8b",
    name: "DeepSeek R1 8B (Ollama)",
    badge_label: "Penalaran Offline",
    description: "Penalaran matematika dan logika chain-of-thought offline di perangkat PC Anda tanpa koneksi internet.",
  },
  {
    provider: "ollama",
    model_id: "llama4:scout",
    name: "Meta Llama 4 Scout (Ollama)",
    badge_label: "Flagship Lokal Meta",
    description: "Arsitektur Mixture-of-Experts Llama 4 untuk PC/Mac berspesifikasi memori tinggi.",
  },

  // LM Studio
  {
    provider: "lmstudio",
    model_id: "qwen3.8-8b-instruct",
    name: "Qwen 3.8 8B Instruct (LM Studio)",
    badge_label: "Server Lokal OpenAI",
    description: "Integrasi server lokal LM Studio untuk menjalankan Qwen 3.8 8B dengan akselerasi penuh GPU/MLX.",
    is_recommended: true,
  },
  {
    provider: "lmstudio",
    model_id: "gemma-4-12b-it",
    name: "Google Gemma 4 12B Instruct (LM Studio)",
    badge_label: "Multimodal Lokal Gen-4",
    description: "Model multimodal Gemma 4 12B melalui endpoint OpenAI lokal LM Studio.",
  },
  {
    provider: "lmstudio",
    model_id: "deepseek-r1-distill-qwen-14b",
    name: "DeepSeek R1 Distill 14B (LM Studio)",
    badge_label: "Reasoning Lokal",
    description: "Menjalankan model penalaran DeepSeek R1 14B secara lokal melalui antarmuka LM Studio.",
  },
];

const CLOUD_PROVIDERS: {
  id: ModelProvider;
  name: string;
  desc: string;
  placeholder: string;
  link: string;
  defaultTestModel: string;
}[] = [
  {
    id: "gemini",
    name: "Google Gemini",
    desc: "Gemini 4 Carbon, 4 Argon & 3.8 Flash — Frontier multimodal & ideal untuk Supervisor",
    placeholder: "AIzaSy...",
    link: "https://aistudio.google.com/app/apikey",
    defaultTestModel: "gemini-3.8-flash",
  },
  {
    id: "anthropic",
    name: "Anthropic Claude",
    desc: "Claude Fable 5.2, Opus 5.5 & Sonnet 5.5 — Penalaran mendalam & agen otonom",
    placeholder: "sk-ant-...",
    link: "https://console.anthropic.com/",
    defaultTestModel: "claude-sonnet-5-5",
  },
  {
    id: "deepseek",
    name: "DeepSeek API",
    desc: "DeepSeek V4 Pro, V4.1 Flash & R1 — Sangat hemat token untuk formula Excel & data",
    placeholder: "sk-...",
    link: "https://platform.deepseek.com/",
    defaultTestModel: "deepseek-flash",
  },
  {
    id: "openai",
    name: "OpenAI",
    desc: "GPT-6.2 Astra, GPT-6.2 Sol & GPT-6 Luna — Standar industri kecerdasan buatan",
    placeholder: "sk-...",
    link: "https://platform.openai.com/api-keys",
    defaultTestModel: "gpt-6.2-sol",
  },
  {
    id: "groq",
    name: "Groq Cloud",
    desc: "Llama 4 Maverick, Qwen 3.8 & DeepSeek R1 — Inferensi ultra-cepat berbasis chip LPU",
    placeholder: "gsk_...",
    link: "https://console.groq.com/keys",
    defaultTestModel: "meta-llama/llama-4-scout-17b-16e-instruct",
  },
  {
    id: "openrouter",
    name: "OpenRouter",
    desc: "Akses fleksibel ke Claude 5.5, Gemini 4, GPT-6.2 & 200+ model dalam satu kunci API",
    placeholder: "sk-or-...",
    link: "https://openrouter.ai/keys",
    defaultTestModel: "openrouter/auto",
  },
];

type SettingsTab = "models" | "workspaces" | "permissions" | "analytics";

export const FeatureSectionsView: React.FC = () => {
  const {
    activeNav,
    engineHealth,
    totalTokensUsed,
    totalTokensSaved,
    workspaces,
    activeWorkspaceId,
    setActiveWorkspace,
    addWorkspaceFolder,
    removeWorkspaceFolder,
    updateWorkspacePermissions,
    syncWithBackendEngine,
  } = useAksaStore();

  const [activeTab, setActiveTab] = useState<SettingsTab>("models");

  // API Key State
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({
    gemini: "",
    anthropic: "",
    deepseek: "",
    openai: "",
    groq: "",
    openrouter: "",
  });
  const [configuredProviders, setConfiguredProviders] = useState<Record<string, boolean>>({});
  const [savedNotice, setSavedNotice] = useState<string | null>(null);
  const [isSavingKey, setIsSavingKey] = useState<string | null>(null);
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({});
  const [testingStatus, setTestingStatus] = useState<
    Record<string, { loading: boolean; ok?: boolean; message?: string }>
  >({});

  // Custom Model Form State
  const [customProvider, setCustomProvider] = useState<ModelProvider>("gemini");
  const [customModelId, setCustomModelId] = useState("");
  const [customModelSuccess, setCustomModelSuccess] = useState<string | null>(null);

  // New Workspace Form State
  const [newFolderPath, setNewFolderPath] = useState("");
  const [newFolderName, setNewFolderName] = useState("");
  const [folderNotice, setFolderNotice] = useState<string | null>(null);

  // Local AI State
  const [isCheckingOllama, setIsCheckingOllama] = useState(false);
  const [copiedCmd, setCopiedCmd] = useState(false);

  const activeWorkspace = workspaces.find((w) => w.id === activeWorkspaceId) ?? workspaces[0];

  const loadProviderStatus = async () => {
    const details = await fetchProviderDetails();
    if (details) {
      setConfiguredProviders(details.configured);
      if (details.apiKeys) {
        setApiKeys((prev) => ({ ...details.apiKeys, ...prev }));
      }
    } else {
      const status = await fetchConfiguredProviders();
      if (status) {
        setConfiguredProviders(status);
      }
    }
  };

  useEffect(() => {
    void loadProviderStatus();
  }, []);

  if (activeNav === "pengetahuan_rag") return <KnowledgeBaseView />;
  if (activeNav === "telegram") return <TelegramGatewayView />;
  if (activeNav === "aplikasi") return <ApplicationsView />;
  if (activeNav === "keahlian") return <SkillsView />;
  if (activeNav === "izin_pc") return <PermissionsAndPCView />;

  const handleSaveKey = async (provider: string) => {
    const key = apiKeys[provider]?.trim() ?? "";
    setIsSavingKey(provider);
    await saveProviderApiKey(provider, key);
    await loadProviderStatus();
    setSavedNotice(`Kunci API ${provider.toUpperCase()} berhasil disimpan.`);
    setIsSavingKey(null);
    setTimeout(() => setSavedNotice(null), 3500);
  };

  const handleTestKey = async (provider: ModelProvider, defaultModel: string) => {
    setTestingStatus((prev) => ({
      ...prev,
      [provider]: { loading: true },
    }));

    // If key entered in input, save first
    if (apiKeys[provider]?.trim()) {
      await saveProviderApiKey(provider, apiKeys[provider].trim());
      await loadProviderStatus();
    }

    const res = await testModelConnectionRemote({
      provider,
      model_id: defaultModel,
    });

    if (res.ok) {
      setTestingStatus((prev) => ({
        ...prev,
        [provider]: {
          loading: false,
          ok: true,
          message: `Berhasil terhubung ke ${defaultModel}! (Respon: "${res.reply?.slice(0, 30)}...")`,
        },
      }));
    } else {
      setTestingStatus((prev) => ({
        ...prev,
        [provider]: {
          loading: false,
          ok: false,
          message: res.error || "Gagal menghubungi model. Periksa kembali kunci API Anda.",
        },
      }));
    }

    setTimeout(() => {
      setTestingStatus((prev) => {
        const next = { ...prev };
        delete next[provider];
        return next;
      });
    }, 6000);
  };

  const handleAddCustomModel = (e: React.FormEvent) => {
    e.preventDefault();
    if (!customModelId.trim()) return;
    setCustomModelSuccess(
      `Model kustom "${customModelId.trim()}" (${customProvider}) siap digunakan di Tim Agen!`
    );
    setCustomModelId("");
    setTimeout(() => setCustomModelSuccess(null), 4000);
  };

  const handleAddWorkspace = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newFolderPath.trim()) return;
    addWorkspaceFolder(newFolderPath.trim(), newFolderName.trim() || undefined);
    setFolderNotice(`Folder Kerja "${newFolderPath.trim()}" berhasil ditambahkan.`);
    setNewFolderPath("");
    setNewFolderName("");
    setTimeout(() => setFolderNotice(null), 4000);
  };

  const handleCopyOllamaCommand = () => {
    void navigator.clipboard.writeText("ollama run qwen3.8:8b");
    setCopiedCmd(true);
    setTimeout(() => setCopiedCmd(false), 2000);
  };

  const handleCheckOllamaAgain = async () => {
    setIsCheckingOllama(true);
    await syncWithBackendEngine();
    setTimeout(() => setIsCheckingOllama(false), 500);
  };

  const hasTokenActivity = totalTokensUsed + totalTokensSaved > 0;
  const savingsPct = hasTokenActivity
    ? Math.round((totalTokensSaved / (totalTokensUsed + totalTokensSaved)) * 100)
    : 0;

  return (
    <div className="flex-1 p-6 md:p-8 overflow-y-auto bg-[#191918]">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-white/[0.06]">
          <div>
            <h1 className="text-lg font-semibold text-zinc-100 flex items-center gap-2">
              <Settings size={18} className="text-[#D97757]" />
              Pengaturan Sistem &amp; Preferensi AKSA
            </h1>
            <p className="text-xs text-zinc-400 mt-1">
              Atur model AI cloud &amp; lokal, tentukan folder kerja PC yang diizinkan, dan kelola izin keamanan sandbox.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-xl bg-white/[0.03] border border-white/[0.08] px-3 py-1.5 text-xs text-zinc-400">
              <Shield size={13} className="text-emerald-400" />
              <span>Keamanan Aktif</span>
            </span>
          </div>
        </div>

        {/* Global Toast / Notice */}
        {savedNotice && (
          <div className="rounded-xl bg-emerald-500/10 border border-emerald-500/30 p-3.5 text-xs text-emerald-300 flex items-center gap-2 animate-in fade-in">
            <CheckCircle2 size={15} className="shrink-0 text-emerald-400" />
            <span>{savedNotice}</span>
          </div>
        )}

        {/* Top Navigation Tabs */}
        <div className="flex flex-wrap items-center gap-2 border-b border-white/[0.06] pb-3">
          <button
            onClick={() => setActiveTab("models")}
            className={`flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-medium transition-all ${
              activeTab === "models"
                ? "bg-[#262624] text-zinc-100 border border-white/[0.12] shadow-sm"
                : "text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.03]"
            }`}
          >
            <Cpu size={14} className={activeTab === "models" ? "text-[#D97757]" : ""} />
            <span>Model AI &amp; Kunci API</span>
            <span className="rounded-full bg-white/[0.06] px-2 py-0.2 text-[10px] text-zinc-400">
              {PRELOADED_MODELS.length}+ Model
            </span>
          </button>

          <button
            onClick={() => setActiveTab("workspaces")}
            className={`flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-medium transition-all ${
              activeTab === "workspaces"
                ? "bg-[#262624] text-zinc-100 border border-white/[0.12] shadow-sm"
                : "text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.03]"
            }`}
          >
            <FolderOpen size={14} className={activeTab === "workspaces" ? "text-emerald-400" : ""} />
            <span>Lokasi Folder Kerja PC</span>
            <span className="rounded-full bg-white/[0.06] px-2 py-0.2 text-[10px] text-zinc-400">
              {workspaces.length} Folder
            </span>
          </button>

          <button
            onClick={() => setActiveTab("permissions")}
            className={`flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-medium transition-all ${
              activeTab === "permissions"
                ? "bg-[#262624] text-zinc-100 border border-white/[0.12] shadow-sm"
                : "text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.03]"
            }`}
          >
            <ShieldCheck size={14} className={activeTab === "permissions" ? "text-sky-400" : ""} />
            <span>Izin &amp; Keamanan PC</span>
          </button>

          <button
            onClick={() => setActiveTab("analytics")}
            className={`flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-medium transition-all ${
              activeTab === "analytics"
                ? "bg-[#262624] text-zinc-100 border border-white/[0.12] shadow-sm"
                : "text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.03]"
            }`}
          >
            <Zap size={14} className={activeTab === "analytics" ? "text-amber-400" : ""} />
            <span>Efisiensi Token</span>
          </button>
        </div>

        {/* TAB 1: MODEL AI & KUNCI API */}
        {activeTab === "models" && (
          <div className="space-y-8">
            {/* 1.1 Form Koneksi Kunci API Cloud */}
            <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 md:p-6 space-y-5">
              <div className="flex items-center justify-between">
                <div className="space-y-1">
                  <h2 className="text-sm font-semibold text-zinc-100 flex items-center gap-2">
                    <KeyRound size={16} className="text-[#D97757]" />
                    Kunci API Model
                  </h2>
                  <p className="text-xs text-zinc-400">
                    Masukkan API Key model AI cloud untuk menghubungkan agen kerja AKSA.
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {CLOUD_PROVIDERS.map((prov) => {
                  const isConnected = Boolean(configuredProviders[prov.id]);
                  const testState = testingStatus[prov.id];
                  const currentVal = apiKeys[prov.id] ?? "";

                  return (
                    <div
                      key={prov.id}
                      className="rounded-xl bg-[#262624] border border-white/[0.06] p-4 space-y-3 flex flex-col justify-between"
                    >
                      <div className="space-y-1.5">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <ProviderIcon provider={prov.id} size={15} />
                            <span className="text-xs font-semibold text-zinc-200">{prov.name}</span>
                          </div>
                          <span
                            className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium border ${
                              isConnected
                                ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                                : "bg-white/[0.03] text-zinc-500 border-white/[0.06]"
                            }`}
                          >
                            <span
                              className={`w-1.5 h-1.5 rounded-full ${
                                isConnected ? "bg-emerald-400" : "bg-zinc-600"
                              }`}
                            />
                            {isConnected ? "Terkoneksi" : "Belum Ada Kunci"}
                          </span>
                        </div>
                        <p className="text-[11px] text-zinc-400 leading-relaxed">{prov.desc}</p>
                      </div>

                      <div className="space-y-2 pt-1">
                        <div className="flex items-center gap-2">
                          <div className="relative flex-1 flex items-center">
                            <input
                              type={showKeys[prov.id] ? "text" : "password"}
                              value={currentVal}
                              onChange={(e) =>
                                setApiKeys((prev) => ({ ...prev, [prov.id]: e.target.value }))
                              }
                              placeholder={prov.placeholder}
                              autoComplete="off"
                              spellCheck={false}
                              className="w-full rounded-lg bg-[#191918] border border-white/[0.08] pl-3 pr-8 py-1.5 text-xs text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-[#D97757]"
                            />
                            <button
                              type="button"
                              onClick={() =>
                                setShowKeys((prev) => ({
                                  ...prev,
                                  [prov.id]: !prev[prov.id],
                                }))
                              }
                              title={showKeys[prov.id] ? "Sembunyikan Kunci" : "Tampilkan Kunci"}
                              className="absolute right-2 text-zinc-500 hover:text-zinc-300 transition-colors p-0.5"
                            >
                              {showKeys[prov.id] ? <EyeOff size={13} /> : <Eye size={13} />}
                            </button>
                          </div>
                          <button
                            onClick={() => void handleSaveKey(prov.id)}
                            disabled={isSavingKey === prov.id}
                            className="rounded-lg bg-white/[0.06] hover:bg-[#D97757] hover:text-white border border-white/[0.08] px-3 py-1.5 text-xs font-medium text-zinc-200 transition-colors shrink-0"
                          >
                            {isSavingKey === prov.id ? "Menyimpan..." : "Simpan"}
                          </button>
                          <button
                            onClick={() => void handleTestKey(prov.id, prov.defaultTestModel)}
                            disabled={testState?.loading}
                            title="Uji apakah kunci API valid dan terhubung"
                            className="rounded-lg bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] px-2.5 py-1.5 text-xs font-medium text-zinc-300 transition-colors flex items-center gap-1 shrink-0"
                          >
                            <Play size={11} className={testState?.loading ? "animate-spin" : ""} />
                            <span>Uji</span>
                          </button>
                        </div>

                        {/* Test Connection Result Feedback */}
                        {testState && !testState.loading && (
                          <div
                            className={`rounded-lg p-2 text-[11px] flex items-start gap-1.5 ${
                              testState.ok
                                ? "bg-emerald-500/10 text-emerald-300 border border-emerald-500/20"
                                : "bg-rose-500/10 text-rose-300 border border-rose-500/20"
                            }`}
                          >
                            {testState.ok ? (
                              <CheckCircle2 size={13} className="shrink-0 mt-0.5 text-emerald-400" />
                            ) : (
                              <AlertCircle size={13} className="shrink-0 mt-0.5 text-rose-400" />
                            )}
                            <span className="leading-tight">{testState.message}</span>
                          </div>
                        )}

                        <div className="flex items-center justify-between text-[10.5px] text-zinc-500">
                          <span>Model Tes: {prov.defaultTestModel}</span>
                          <a
                            href={prov.link}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-1 text-zinc-400 hover:text-zinc-200 transition-colors"
                          >
                            <span>Dapatkan Kunci API</span>
                            <ExternalLink size={10} />
                          </a>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* 1.2 Katalog Lengkap Model AI Terbaru (Sudah Pre-Loaded) */}
            <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 md:p-6 space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-white/[0.06] pb-3">
                <div className="space-y-0.5">
                  <h2 className="text-sm font-semibold text-zinc-100 flex items-center gap-2">
                    <Layers size={16} className="text-emerald-400" />
                    Katalog Model AI Modern Siap Pakai (Otomatis Terpasang)
                  </h2>
                  <p className="text-xs text-zinc-400">
                    Semua model terbaru di bawah ini sudah tersedia langsung di menu <strong>Tim Agen</strong> tanpa perlu konfigurasi manual.
                  </p>
                </div>
                <span className="text-xs text-zinc-400 font-mono">
                  Total {PRELOADED_MODELS.length} Model Cloud Siap Pakai
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 pt-1">
                {PRELOADED_MODELS.map((m) => (
                  <div
                    key={`${m.provider}_${m.model_id}`}
                    className="rounded-xl bg-[#262624] border border-white/[0.06] hover:border-white/[0.14] p-3.5 space-y-2 transition-all"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-1.5 min-w-0">
                        <ProviderIcon provider={m.provider} size={14} />
                        <span className="text-xs font-semibold text-zinc-200 truncate">{m.name}</span>
                      </div>
                      <span
                        className={`rounded px-1.5 py-0.5 text-[9.5px] font-medium shrink-0 ${
                          m.is_recommended
                            ? "bg-[#D97757]/20 text-[#D97757] border border-[#D97757]/30"
                            : "bg-white/[0.05] text-zinc-400"
                        }`}
                      >
                        {m.badge_label}
                      </span>
                    </div>

                    <p className="text-[11px] text-zinc-400 leading-relaxed line-clamp-2">
                      {m.description}
                    </p>

                    <div className="flex items-center justify-between pt-1 border-t border-white/[0.04] text-[10px] text-zinc-500 font-mono">
                      <span className="truncate">{m.model_id}</span>
                      <span className="uppercase text-zinc-400">{m.provider}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* 1.3 Form Tambah Model Kustom Manual */}
            <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 md:p-6 space-y-4">
              <div className="space-y-1">
                <h2 className="text-sm font-semibold text-zinc-100 flex items-center gap-2">
                  <Sliders size={16} className="text-sky-400" />
                  Tambah Model Kustom Secara Manual (Opsional)
                </h2>
                <p className="text-xs text-zinc-400">
                  Ingin menggunakan model baru yang baru rilis, versi preview (misal <code>o3-mini</code> atau <code>gemini-3.1-pro-preview</code>), atau model fine-tuned pribadi? Daftarkan ID model di sini.
                </p>
              </div>

              {customModelSuccess && (
                <div className="rounded-xl bg-emerald-500/10 border border-emerald-500/25 p-3 text-xs text-emerald-300 flex items-center gap-2">
                  <CheckCircle2 size={14} className="text-emerald-400" />
                  <span>{customModelSuccess}</span>
                </div>
              )}

              <form onSubmit={handleAddCustomModel} className="flex flex-col sm:flex-row gap-3">
                <select
                  value={customProvider}
                  onChange={(e) => setCustomProvider(e.target.value as ModelProvider)}
                  className="rounded-xl bg-[#262624] border border-white/[0.09] px-3.5 py-2 text-xs text-zinc-200 focus:outline-none focus:border-[#D97757]"
                >
                  <option value="gemini">Google Gemini</option>
                  <option value="anthropic">Anthropic Claude</option>
                  <option value="openai">OpenAI</option>
                  <option value="deepseek">DeepSeek</option>
                  <option value="groq">Groq</option>
                  <option value="openrouter">OpenRouter</option>
                  <option value="ollama">Ollama (Lokal)</option>
                  <option value="lmstudio">LM Studio (Lokal)</option>
                </select>

                <input
                  type="text"
                  value={customModelId}
                  onChange={(e) => setCustomModelId(e.target.value)}
                  placeholder="Contoh: gemini-4-carbon, claude-opus-5-5, atau gpt-6.2-astra"
                  className="flex-1 rounded-xl bg-[#262624] border border-white/[0.09] px-3.5 py-2 text-xs text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-[#D97757]"
                />

                <button
                  type="submit"
                  disabled={!customModelId.trim()}
                  className="rounded-xl bg-[#D97757] hover:bg-[#c96a4b] disabled:opacity-40 disabled:cursor-not-allowed text-white px-4 py-2 text-xs font-medium transition-colors flex items-center justify-center gap-1.5 shrink-0"
                >
                  <Plus size={14} />
                  <span>Daftarkan Model Kustom</span>
                </button>
              </form>
            </div>

            {/* 1.4 AI Lokal (Ollama & LM Studio) */}
            <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Cpu size={16} className="text-emerald-400" />
                  <span className="text-xs font-semibold text-zinc-100">
                    Server AI Lokal Komputer Anda (Ollama &amp; LM Studio — 100% Gratis &amp; Offline)
                  </span>
                </div>
                <button
                  onClick={() => void handleCheckOllamaAgain()}
                  disabled={isCheckingOllama}
                  title="Periksa ulang status koneksi Ollama lokal"
                  className="rounded-lg p-1.5 text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.04] transition-colors"
                >
                  <RefreshCw size={13} className={isCheckingOllama ? "animate-spin" : ""} />
                </button>
              </div>

              <div className="rounded-xl bg-[#262624] border border-white/[0.06] p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span
                      className={`inline-block w-2 h-2 rounded-full ${
                        engineHealth.ollama_online ? "bg-emerald-400" : "bg-zinc-600"
                      }`}
                    />
                    <span className="text-xs font-semibold text-zinc-200">
                      {engineHealth.ollama_online
                        ? "Ollama Terdeteksi Aktif di http://127.0.0.1:11434"
                        : "Ollama Sedang Tidak Berjalan (Opsional)"}
                    </span>
                  </div>
                  <p className="text-[11px] text-zinc-400">
                    {engineHealth.ollama_online && engineHealth.ollama_models.length > 0
                      ? `Model terpasang: ${engineHealth.ollama_models.join(", ")}`
                      : "Jalankan Ollama di PC Anda jika ingin menjalankan sub-agen tanpa biaya API."}
                  </p>
                </div>

                <button
                  onClick={handleCopyOllamaCommand}
                  className="rounded-lg bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.07] px-3 py-1.5 text-[11px] text-zinc-300 font-mono transition-colors flex items-center gap-1.5 shrink-0"
                >
                  {copiedCmd ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
                  <span>{copiedCmd ? "Tersalin!" : "ollama run qwen3.8:8b"}</span>
                </button>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: LOKASI FOLDER KERJA PC */}
        {activeTab === "workspaces" && (
          <div className="space-y-6">
            {/* 2.1 Folder Aktif Highlight Card */}
            <div className="rounded-2xl bg-gradient-to-br from-[#262624] to-[#21211F] border border-emerald-500/30 p-5 md:p-6 space-y-3">
              <div className="flex items-center justify-between">
                <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/15 border border-emerald-500/30 px-3 py-1 text-xs font-semibold text-emerald-400">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  Folder Kerja Aktif Saat Ini
                </span>
                <span className="text-xs text-zinc-400 font-mono">
                  Digunakan di Ruang Kerja &amp; Sub-Agen
                </span>
              </div>

              <div className="space-y-1">
                <h3 className="text-base font-semibold text-zinc-100">{activeWorkspace?.name}</h3>
                <div className="text-xs font-mono text-zinc-300 bg-black/40 border border-white/[0.08] rounded-xl px-3.5 py-2.5 break-all">
                  {activeWorkspace?.folder_path}
                </div>
              </div>

              <p className="text-xs text-zinc-400 leading-relaxed pt-1">
                Seluruh file baru (seperti <code>.xlsx</code>, <code>.docx</code>, <code>.pptx</code>, <code>.pdf</code>) yang dibuat oleh tim agen akan langsung disimpan di dalam folder ini.
              </p>
            </div>

            {/* 2.2 Form Tambah Folder Kerja Baru */}
            <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 md:p-6 space-y-4">
              <div className="space-y-1">
                <h2 className="text-sm font-semibold text-zinc-100 flex items-center gap-2">
                  <FolderPlus size={16} className="text-[#D97757]" />
                  Tambahkan Lokasi Folder Kerja Baru
                </h2>
                <p className="text-xs text-zinc-400">
                  Masukkan path folder di komputer Anda (misal folder proyek kantor atau laporan).
                </p>
              </div>

              {folderNotice && (
                <div className="rounded-xl bg-emerald-500/10 border border-emerald-500/25 p-3 text-xs text-emerald-300 flex items-center gap-2">
                  <CheckCircle2 size={14} className="text-emerald-400" />
                  <span>{folderNotice}</span>
                </div>
              )}

              <form onSubmit={handleAddWorkspace} className="space-y-3">
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div className="sm:col-span-2 space-y-1">
                    <label className="text-[11px] font-medium text-zinc-400">
                      Path Direktori Lengkap di PC
                    </label>
                    <input
                      type="text"
                      value={newFolderPath}
                      onChange={(e) => setNewFolderPath(e.target.value)}
                      placeholder="Contoh: /Users/nama/Documents/Laporan atau C:\Proyek\Data"
                      className="w-full rounded-xl bg-[#262624] border border-white/[0.09] px-3.5 py-2 text-xs text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-[#D97757]"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-[11px] font-medium text-zinc-400">Nama Alias Folder (Opsional)</label>
                    <input
                      type="text"
                      value={newFolderName}
                      onChange={(e) => setNewFolderName(e.target.value)}
                      placeholder="Contoh: Berkas Keuangan 2026"
                      className="w-full rounded-xl bg-[#262624] border border-white/[0.09] px-3.5 py-2 text-xs text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-[#D97757]"
                    />
                  </div>
                </div>

                <div className="flex justify-end pt-1">
                  <button
                    type="submit"
                    disabled={!newFolderPath.trim()}
                    className="rounded-xl bg-[#D97757] hover:bg-[#c96a4b] disabled:opacity-40 disabled:cursor-not-allowed text-white px-4 py-2 text-xs font-medium transition-colors flex items-center gap-1.5"
                  >
                    <Plus size={14} />
                    <span>Otorisasikan &amp; Tambah Folder</span>
                  </button>
                </div>
              </form>
            </div>

            {/* 2.3 Daftar Folder Terdaftar & Kontrol Hak Akses Granular */}
            <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 md:p-6 space-y-4">
              <div className="flex items-center justify-between border-b border-white/[0.06] pb-3">
                <div className="space-y-0.5">
                  <h3 className="text-sm font-semibold text-zinc-100 flex items-center gap-2">
                    <FolderLock size={15} className="text-emerald-400" />
                    Daftar Folder Kerja Diotorisasi ({workspaces.length})
                  </h3>
                  <p className="text-xs text-zinc-400">
                    Folder di luar daftar ini otomatis diblokir oleh Python Sandbox Engine demi keamanan Anda.
                  </p>
                </div>
              </div>

              <div className="space-y-3 pt-1">
                {workspaces.map((ws) => {
                  const isActive = ws.id === activeWorkspaceId;

                  return (
                    <div
                      key={ws.id}
                      className={`rounded-xl p-4 border transition-all flex flex-col md:flex-row md:items-center justify-between gap-4 ${
                        isActive
                          ? "bg-[#262624] border-emerald-500/40 ring-1 ring-emerald-500/20"
                          : "bg-[#21211F] border-white/[0.07] hover:border-white/[0.14]"
                      }`}
                    >
                      <div className="space-y-1 min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-semibold text-zinc-100">{ws.name}</span>
                          {isActive && (
                            <span className="rounded-full bg-emerald-500/15 border border-emerald-500/30 px-2 py-0.2 text-[10px] font-medium text-emerald-400">
                              Aktif
                            </span>
                          )}
                        </div>
                        <div className="text-[11px] font-mono text-zinc-400 break-all">
                          {ws.folder_path}
                        </div>
                      </div>

                      <div className="flex flex-wrap items-center gap-2 shrink-0">
                        {/* Granular Permission Toggles */}
                        <label className="flex items-center gap-1.5 rounded-lg bg-[#191918] border border-white/[0.07] px-2.5 py-1 text-[11px] text-zinc-300 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={ws.allow_read}
                            onChange={(e) =>
                              updateWorkspacePermissions(ws.id, { allow_read: e.target.checked })
                            }
                            className="accent-emerald-500"
                          />
                          <span>Baca Berkas</span>
                        </label>

                        <label className="flex items-center gap-1.5 rounded-lg bg-[#191918] border border-white/[0.07] px-2.5 py-1 text-[11px] text-zinc-300 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={ws.allow_write}
                            onChange={(e) =>
                              updateWorkspacePermissions(ws.id, { allow_write: e.target.checked })
                            }
                            className="accent-emerald-500"
                          />
                          <span>Tulis Dokumen</span>
                        </label>

                        <label className="flex items-center gap-1.5 rounded-lg bg-[#191918] border border-white/[0.07] px-2.5 py-1 text-[11px] text-zinc-300 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={ws.allow_execute}
                            onChange={(e) =>
                              updateWorkspacePermissions(ws.id, { allow_execute: e.target.checked })
                            }
                            className="accent-emerald-500"
                          />
                          <span>Eksekusi Python</span>
                        </label>

                        {!isActive && (
                          <button
                            onClick={() => setActiveWorkspace(ws.id)}
                            className="rounded-lg bg-white/[0.06] hover:bg-emerald-600 hover:text-white px-3 py-1 text-xs font-medium text-zinc-200 transition-colors"
                          >
                            Pilih Aktif
                          </button>
                        )}

                        {workspaces.length > 1 && (
                          <button
                            onClick={() => removeWorkspaceFolder(ws.id)}
                            title="Hapus otorisasi folder ini"
                            className="rounded-lg p-1.5 text-zinc-500 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
                          >
                            <Trash2 size={13} />
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* 2.4 Penjelasan Keamanan Sandbox */}
            <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 space-y-2">
              <div className="flex items-center gap-2 text-xs font-semibold text-zinc-200">
                <Info size={14} className="text-[#D97757]" />
                <span>Bagaimana Sistem Keamanan Folder AKSA Melindungi Komputer Anda?</span>
              </div>
              <p className="text-xs text-zinc-400 leading-relaxed">
                AKSA menerapkan prinsip <strong>Path Jail (Sandbox)</strong> di tingkat engine backend. Sub-agen hanya memiliki izin untuk beroperasi di dalam direktori folder yang telah Anda cantumkan di atas. Perintah pembacaan atau penulisan yang mencoba mengakses file sistem, folder pengguna lain, atau disk luar akan langsung ditolak secara otomatis.
              </p>
            </div>
          </div>
        )}

        {/* TAB 3: IZIN & KEAMANAN PC */}
        {activeTab === "permissions" && <PermissionsTabContent />}

        {/* TAB 4: EFISIENSI TOKEN */}
        {activeTab === "analytics" && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 space-y-2">
                <span className="text-xs text-zinc-400 flex items-center gap-1.5">
                  <Zap size={14} className="text-emerald-400" /> Rasio Penghematan Token
                </span>
                <div className="text-3xl font-bold tracking-tight text-emerald-400">
                  {hasTokenActivity ? `${savingsPct}% Hemat` : "0%"}
                </div>
                <p className="text-xs text-zinc-500">
                  {hasTokenActivity
                    ? "Isolasi Konteks Sub-Agen & Lazy Tool Injection aktif"
                    : "Belum ada tugas dijalankan di Ruang Kerja"}
                </p>
              </div>

              <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 space-y-2">
                <span className="text-xs text-zinc-400">Total Token Dihemat</span>
                <div className="text-3xl font-bold tracking-tight text-zinc-100">
                  {formatNumberID(totalTokensSaved)} Token
                </div>
                <p className="text-xs text-zinc-500">
                  Token dokumen mentah yang diproses sub-agen tanpa membebani supervisor.
                </p>
              </div>

              <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 space-y-2">
                <span className="text-xs text-zinc-400">Token Manajer Utama (Supervisor)</span>
                <div className="text-3xl font-bold tracking-tight text-zinc-100">
                  {formatNumberID(totalTokensUsed)} Token
                </div>
                <p className="text-xs text-zinc-500">
                  Supervisor hanya mengonsumsi intisari ringkas hasil kerja.
                </p>
              </div>
            </div>

            <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 space-y-3">
              <h3 className="text-xs font-semibold text-zinc-200">
                Arsitektur Efisiensi Token Bertingkat (Token Economy)
              </h3>
              <p className="text-xs text-zinc-400 leading-relaxed">
                Tanpa isolasi konteks, mengirimkan instruksi beserta ratusan baris data dokumen ke model utama akan menghabiskan puluhan ribu token dalam satu kali percakapan. AKSA memecah tugas ke sub-agen spesialis yang bekerja di ruang memori terisolasi, menyaring hasilnya, dan hanya menyerahkan intisari eksekutif kepada Manajer Utama.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

// Reusable Permissions Tab Content
const PermissionsTabContent: React.FC = () => {
  const {
    emergencyStopActive,
    toggleEmergencyStop,
    requestSampleApproval,
  } = useAksaStore();

  return (
    <div className="space-y-6">
      {/* Banner & Emergency Stop */}
      <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 md:p-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="space-y-1">
          <h2 className="text-sm font-semibold text-zinc-100 flex items-center gap-2">
            <ShieldCheck size={18} className="text-emerald-400" />
            Keamanan Tingkat Sistem &amp; Tombol Stop Darurat Global
          </h2>
          <p className="text-xs text-zinc-400">
            Kendalikan hak akses eksekusi PC, uji simulasi konfirmasi HITL, atau aktifkan pemutus darurat seketika.
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={() => void requestSampleApproval()}
            className="rounded-xl bg-amber-500/15 hover:bg-amber-500/25 border border-amber-500/30 px-3.5 py-2 text-xs font-medium text-amber-300 transition-colors"
          >
            Uji Dialog Konfirmasi (HITL)
          </button>
          <button
            onClick={() => void toggleEmergencyStop(!emergencyStopActive)}
            className={`rounded-xl px-4 py-2 text-xs font-semibold flex items-center gap-1.5 border transition-colors ${
              emergencyStopActive
                ? "bg-emerald-600/20 border-emerald-500/40 text-emerald-300"
                : "bg-rose-600/20 hover:bg-rose-600/30 border-rose-500/40 text-rose-300"
            }`}
          >
            <OctagonAlert size={14} />
            <span>
              {emergencyStopActive ? "Batalkan Stop Darurat" : "Stop Darurat (Ctrl+Shift+Q)"}
            </span>
          </button>
        </div>
      </div>

      {/* Security Policies Overview */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 space-y-2">
          <div className="flex items-center gap-2 text-xs font-semibold text-zinc-200">
            <FolderLock size={15} className="text-[#D97757]" />
            <span>Sandbox Path Jail</span>
          </div>
          <p className="text-xs text-zinc-400 leading-relaxed">
            Semua operasi berkas divalidasi di tingkat Python menggunakan <code>os.path.realpath</code>. Upaya pembacaan path traversal (seperti <code>../../</code>) otomatis dicegah.
          </p>
        </div>

        <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 space-y-2">
          <div className="flex items-center gap-2 text-xs font-semibold text-zinc-200">
            <Shield size={15} className="text-emerald-400" />
            <span>Auto-Backup Dokumen</span>
          </div>
          <p className="text-xs text-zinc-400 leading-relaxed">
            Sebelum sub-agen mengedit atau menimpa dokumen Excel atau Word yang ada, AKSA otomatis menyalin berkas asli ke dalam sub-folder tersembunyi <code>.aksa_backup/</code>.
          </p>
        </div>

        <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 space-y-2">
          <div className="flex items-center gap-2 text-xs font-semibold text-zinc-200">
            <Sparkles size={15} className="text-sky-400" />
            <span>Human-in-the-Loop (HITL)</span>
          </div>
          <p className="text-xs text-zinc-400 leading-relaxed">
            Tindakan yang berisiko tinggi (seperti menjalankan skrip Python eksternal atau kontrol mouse) wajib disetujui secara sadar oleh pengguna melalui jendela modal persetujuan.
          </p>
        </div>
      </div>
    </div>
  );
};
