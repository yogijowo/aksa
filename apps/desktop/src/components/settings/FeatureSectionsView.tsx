import React, { useState, useEffect } from "react";
import {
  Settings,
  FolderOpen,
  FolderPlus,
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
  Sliders,
  Plus,
  Trash2,
  Play,
  Layers,
  Info,
  Eye,
  EyeOff,
  Palette,
  HardDrive,
  Globe,
  Wrench,
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
import { PageHeader, SectionHeader, StatusBadge } from "@/components/ui/UXPrimitives";
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
  {
    provider: "gemini",
    model_id: "gemini-4-carbon",
    name: "Gemini 4 Carbon",
    badge_label: "Manajer & Penalaran",
    description: "Model utama Google Gemini 4 untuk koordinasi tim AI dan analisis mendalam.",
    is_recommended: true,
  },
  {
    provider: "gemini",
    model_id: "gemini-4-argon",
    name: "Gemini 4 Argon",
    badge_label: "Multimodal & Dokumen",
    description: "Model unggulan Gemini 4 untuk pemrosesan dokumen panjang dan tugas kompleks.",
    is_recommended: true,
  },
  {
    provider: "gemini",
    model_id: "gemini-3.8-flash",
    name: "Gemini 3.8 Flash",
    badge_label: "Cepat & Tangkas",
    description: "Model harian berkecepatan tinggi untuk respons cepat.",
    is_recommended: true,
  },
  {
    provider: "anthropic",
    model_id: "claude-opus-5-5",
    name: "Claude Opus 5.5",
    badge_label: "Penulisan & Telaah",
    description: "Model utama Claude 5.5 untuk telaah dokumen dan penulisan laporan.",
    is_recommended: true,
  },
  {
    provider: "anthropic",
    model_id: "claude-sonnet-5-5",
    name: "Claude Sonnet 5.5",
    badge_label: "Agen & Aplikasi",
    description: "Kombinasi kecepatan dan ketepatan terbaik untuk pengolahan dokumen & aplikasi.",
    is_recommended: true,
  },
  {
    provider: "openai",
    model_id: "gpt-6.2-astra",
    name: "OpenAI GPT-6.2 Astra",
    badge_label: "Penalaran Lanjut",
    description: "Model unggulan OpenAI generasi GPT-6.2 untuk analisis dan sintesis.",
    is_recommended: true,
  },
  {
    provider: "deepseek",
    model_id: "deepseek-v4-pro",
    name: "DeepSeek V4 Pro",
    badge_label: "Analisis Data & Excel",
    description: "Sangat akurat dan hemat kuota untuk pemodelan tabel Excel serta analisis angka.",
    is_recommended: true,
  },
  {
    provider: "ollama",
    model_id: "qwen3.8:8b",
    name: "Qwen 3.8 8B (Ollama Lokal)",
    badge_label: "Rekomendasi Lokal Gratis",
    description: "Berjalan langsung di komputer Anda tanpa internet dan tanpa biaya kuota API.",
    is_recommended: true,
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
    desc: "Gemini 4 Carbon, 4 Argon & 3.8 Flash",
    placeholder: "AIzaSy...",
    link: "https://aistudio.google.com/app/apikey",
    defaultTestModel: "gemini-3.8-flash",
  },
  {
    id: "anthropic",
    name: "Anthropic Claude",
    desc: "Claude Fable 5.2, Opus 5.5 & Sonnet 5.5",
    placeholder: "sk-ant-...",
    link: "https://console.anthropic.com/",
    defaultTestModel: "claude-sonnet-5-5",
  },
  {
    id: "deepseek",
    name: "DeepSeek",
    desc: "DeepSeek V4 Pro, V4.1 Flash & R1",
    placeholder: "sk-...",
    link: "https://platform.deepseek.com/",
    defaultTestModel: "deepseek-flash",
  },
  {
    id: "openai",
    name: "OpenAI",
    desc: "GPT-6.2 Astra, GPT-6.2 Sol & GPT-6 Luna",
    placeholder: "sk-...",
    link: "https://platform.openai.com/api-keys",
    defaultTestModel: "gpt-6.2-sol",
  },
  {
    id: "groq",
    name: "Groq Cloud",
    desc: "Llama 4 Maverick & Qwen 3.8",
    placeholder: "gsk_...",
    link: "https://console.groq.com/keys",
    defaultTestModel: "meta-llama/llama-4-scout-17b-16e-instruct",
  },
  {
    id: "openrouter",
    name: "OpenRouter",
    desc: "Satu kunci untuk ratusan model AI",
    placeholder: "sk-or-...",
    link: "https://openrouter.ai/keys",
    defaultTestModel: "openrouter/auto",
  },
];

// Section 5.9: 8 Required Settings Categories
type SettingsCategory =
  | "umum"
  | "tampilan"
  | "model_ai"
  | "privasi_data"
  | "penyimpanan"
  | "jaringan"
  | "lanjutan"
  | "info_aplikasi";

const SETTINGS_CATEGORIES: {
  id: SettingsCategory;
  label: string;
  icon: React.ElementType;
}[] = [
  { id: "umum", label: "1. Umum", icon: Settings },
  { id: "tampilan", label: "2. Tampilan", icon: Palette },
  { id: "model_ai", label: "3. Model AI", icon: Cpu },
  { id: "privasi_data", label: "4. Privasi dan data", icon: Shield },
  { id: "penyimpanan", label: "5. Penyimpanan", icon: HardDrive },
  { id: "jaringan", label: "6. Jaringan", icon: Globe },
  { id: "lanjutan", label: "7. Lanjutan", icon: Wrench },
  { id: "info_aplikasi", label: "8. Informasi aplikasi", icon: Info },
];

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
    syncWithBackendEngine,
    setActiveNav,
  } = useAksaStore();

  const [activeCategory, setActiveCategory] = useState<SettingsCategory>("umum");
  const [privacyMode, setPrivacyMode] = useState<"local_first" | "strict_local" | "cloud_allowed">(
    "local_first"
  );
  const [reducedMotion, setReducedMotion] = useState(false);
  const [fontScale, setFontScale] = useState<"standar" | "nyaman">("nyaman");

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
    setSavedNotice(`Kunci layanan ${provider.toUpperCase()} berhasil disimpan di brankas keamanan.`);
    setIsSavingKey(null);
    setTimeout(() => setSavedNotice(null), 3500);
  };

  const handleTestKey = async (provider: ModelProvider, defaultModel: string) => {
    setTestingStatus((prev) => ({
      ...prev,
      [provider]: { loading: true },
    }));

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
          message: `Terhubung dengan baik ke ${defaultModel}.`,
        },
      }));
    } else {
      setTestingStatus((prev) => ({
        ...prev,
        [provider]: {
          loading: false,
          ok: false,
          message: res.error || "Gagal menghubungi layanan. Periksa kembali kunci Anda.",
        },
      }));
    }
  };

  const handleAddCustomModel = (e: React.FormEvent) => {
    e.preventDefault();
    if (!customModelId.trim()) return;
    setCustomModelSuccess(
      `Model kustom "${customModelId.trim()}" (${customProvider}) siap digunakan di Tim AI.`
    );
    setCustomModelId("");
    setTimeout(() => setCustomModelSuccess(null), 4000);
  };

  const handleAddWorkspace = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newFolderPath.trim()) return;
    addWorkspaceFolder(newFolderPath.trim(), newFolderName.trim() || undefined);
    setFolderNotice(`Folder Ruang Kerja "${newFolderPath.trim()}" berhasil ditambahkan.`);
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
        {/* Page Header (Section 5.9 Pengaturan) */}
        <PageHeader
          icon={<Settings size={22} className="text-[#D97757]" />}
          title="Pengaturan AKSA"
          description="Sesuaikan preferensi umum, tampilan, model AI, privasi data, penyimpanan folder, dan jaringan secara terstruktur."
        />

        {savedNotice && (
          <div className="rounded-xl bg-emerald-500/10 border border-emerald-500/30 p-3.5 text-[13px] text-emerald-200 flex items-center gap-2">
            <CheckCircle2 size={16} className="shrink-0 text-emerald-400" />
            <span>{savedNotice}</span>
          </div>
        )}

        {/* 8 Structured Category Tabs (Section 5.9) */}
        <div className="flex flex-wrap items-center gap-2 border-b border-white/[0.07] pb-3">
          {SETTINGS_CATEGORIES.map((cat) => {
            const Icon = cat.icon;
            const isActive = activeCategory === cat.id;
            return (
              <button
                type="button"
                key={cat.id}
                onClick={() => setActiveCategory(cat.id)}
                className={`flex items-center gap-2 rounded-xl px-3.5 py-2 text-[13px] font-medium transition-all ${
                  isActive
                    ? "bg-[#262624] text-zinc-100 border border-white/[0.14] shadow-sm"
                    : "text-zinc-300 hover:text-white hover:bg-white/[0.04]"
                }`}
              >
                <Icon size={15} className={isActive ? "text-[#D97757]" : "text-zinc-400"} />
                <span>{cat.label}</span>
              </button>
            );
          })}
        </div>

        {/* 1. UMUM */}
        {activeCategory === "umum" && (
          <div className="space-y-4">
            <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 md:p-6 space-y-4">
              <SectionHeader
                title="Pengaturan Umum"
                description="Preferensi dasar cara AKSA membantu pekerjaan Anda sehari-hari."
              />

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="rounded-xl bg-[#262624] border border-white/[0.07] p-4 space-y-1.5">
                  <div className="text-[14px] font-semibold text-zinc-100">Bahasa Antarmuka</div>
                  <p className="text-xs text-zinc-300">
                    Bahasa Indonesia (Natural &amp; Mudah Dipahami)
                  </p>
                  <StatusBadge tone="success" label="Aktif sebagai bahasa utama" />
                </div>

                <div className="rounded-xl bg-[#262624] border border-white/[0.07] p-4 space-y-1.5">
                  <div className="text-[14px] font-semibold text-zinc-100">
                    Pemilihan Agen &amp; Model Otomatis
                  </div>
                  <p className="text-xs text-zinc-300">
                    AKSA otomatis memilih agen pendukung dan model AI yang paling sesuai dengan
                    instruksi Anda.
                  </p>
                  <StatusBadge tone="accent" label="Otomatis aktif" />
                </div>
              </div>

              <div className="rounded-xl bg-[#262624] border border-white/[0.07] p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="space-y-1">
                  <div className="text-[14px] font-semibold text-zinc-100">
                    Panduan Pengenalan Awal (Onboarding)
                  </div>
                  <p className="text-xs text-zinc-300">
                    Tampilkan kembali panduan 4 langkah singkat di Ruang Kerja kapan pun Anda
                    membutuhkannya.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    try {
                      localStorage.removeItem("aksa_onboarding_completed");
                    } catch {}
                    setActiveNav("ruang_kerja");
                  }}
                  className="rounded-xl bg-[#D97757] hover:bg-[#c96a4b] px-4 py-2 text-xs font-semibold text-white transition-colors shrink-0"
                >
                  Buka Panduan Awal
                </button>
              </div>
            </div>
          </div>
        )}

        {/* 2. TAMPILAN (Separated cleanly from critical security settings per Section 5.9) */}
        {activeCategory === "tampilan" && (
          <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 md:p-6 space-y-4">
            <SectionHeader
              title="Tampilan & Kenyamanan Baca"
              description="Pengaturan visual antarmuka AKSA. Pengaturan keamanan kritis dipisahkan ke Pusat Akses dan Privasi."
            />

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="rounded-xl bg-[#262624] border border-white/[0.07] p-4 space-y-2">
                <div className="text-[14px] font-semibold text-zinc-100">Tema Warna AKSA</div>
                <p className="text-xs text-zinc-300">
                  Tema Gelap Khas AKSA (<code>#191918</code> dengan aksen hangat{" "}
                  <code>#D97757</code>) untuk kenyamanan mata jangka panjang.
                </p>
                <StatusBadge tone="accent" label="Tema Gelap Aktif" />
              </div>

              <div className="rounded-xl bg-[#262624] border border-white/[0.07] p-4 space-y-2">
                <div className="text-[14px] font-semibold text-zinc-100">Ukuran Teks &amp; Keterbacaan</div>
                <p className="text-xs text-zinc-300">
                  Skala huruf yang jelas dan kontras tinggi agar mudah dibaca pada berbagai ukuran
                  layar.
                </p>
                <div className="flex items-center gap-2 pt-1">
                  <button
                    type="button"
                    onClick={() => setFontScale("nyaman")}
                    className={`rounded-lg px-3 py-1.5 text-xs font-semibold border ${
                      fontScale === "nyaman"
                        ? "bg-[#D97757] text-white border-[#D97757]"
                        : "bg-[#191918] text-zinc-300 border-white/10"
                    }`}
                  >
                    Nyaman (Direkomendasikan)
                  </button>
                  <button
                    type="button"
                    onClick={() => setFontScale("standar")}
                    className={`rounded-lg px-3 py-1.5 text-xs font-semibold border ${
                      fontScale === "standar"
                        ? "bg-[#D97757] text-white border-[#D97757]"
                        : "bg-[#191918] text-zinc-300 border-white/10"
                    }`}
                  >
                    Ringkas
                  </button>
                </div>
              </div>
            </div>

            <label className="flex items-center justify-between rounded-xl bg-[#262624] border border-white/[0.07] p-4 cursor-pointer">
              <div className="space-y-0.5">
                <div className="text-[14px] font-semibold text-zinc-100">
                  Kurangi Efek Gerakan (Reduced Motion)
                </div>
                <p className="text-xs text-zinc-300">
                  Menyederhanakan animasi perpindahan panel bagi pengguna yang sensitif terhadap
                  animasi.
                </p>
              </div>
              <input
                type="checkbox"
                checked={reducedMotion}
                onChange={(e) => setReducedMotion(e.target.checked)}
                className="accent-[#D97757] h-4 w-4"
              />
            </label>
          </div>
        )}

        {/* 3. MODEL AI */}
        {activeCategory === "model_ai" && (
          <div className="space-y-6">
            {/* Local AI (Ollama) */}
            <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 space-y-4">
              <div className="flex items-center justify-between">
                <SectionHeader
                  icon={<Cpu size={18} className="text-emerald-400" />}
                  title="Model AI Lokal di Komputer Anda (Gratis & Tanpa Internet)"
                  description="Gunakan Ollama atau LM Studio jika ingin menjalankan AI sepenuhnya di perangkat Anda."
                />
                <button
                  type="button"
                  onClick={() => void handleCheckOllamaAgain()}
                  disabled={isCheckingOllama}
                  title="Periksa ulang status AI lokal"
                  className="rounded-xl p-2 text-zinc-300 hover:text-white hover:bg-white/[0.06] transition-colors"
                >
                  <RefreshCw size={15} className={isCheckingOllama ? "animate-spin" : ""} />
                </button>
              </div>

              <div className="rounded-xl bg-[#262624] border border-white/[0.07] p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span
                      className={`inline-block w-2.5 h-2.5 rounded-full ${
                        engineHealth.ollama_online ? "bg-emerald-400" : "bg-zinc-500"
                      }`}
                    />
                    <span className="text-[14px] font-semibold text-zinc-100">
                      {engineHealth.ollama_online
                        ? "Ollama Terdeteksi Aktif dan Siap Digunakan"
                        : "Ollama Belum Berjalan (Opsional)"}
                    </span>
                  </div>
                  <p className="text-xs text-zinc-300">
                    {engineHealth.ollama_online && engineHealth.ollama_models.length > 0
                      ? `Model lokal siap pakai: ${engineHealth.ollama_models.join(", ")}`
                      : "Anda tetap dapat menggunakan penyedia AI Cloud di bawah ini."}
                  </p>
                </div>

                <button
                  type="button"
                  onClick={handleCopyOllamaCommand}
                  className="rounded-xl bg-white/[0.06] hover:bg-white/[0.12] border border-white/[0.1] px-3.5 py-2 text-xs text-zinc-200 font-mono transition-colors flex items-center gap-1.5 shrink-0"
                >
                  {copiedCmd ? (
                    <Check size={13} className="text-emerald-400" />
                  ) : (
                    <Copy size={13} />
                  )}
                  <span>{copiedCmd ? "Perintah Disalin!" : "ollama run qwen3.8:8b"}</span>
                </button>
              </div>
            </div>

            {/* Cloud AI Providers */}
            <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 md:p-6 space-y-5">
              <SectionHeader
                icon={<KeyRound size={18} className="text-[#D97757]" />}
                title="Penyedia AI Cloud"
                description="Hubungkan kunci layanan AI pilihan Anda. Kunci disimpan terenkripsi di brankas keamanan perangkat."
              />

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {CLOUD_PROVIDERS.map((prov) => {
                  const isConnected = Boolean(configuredProviders[prov.id]);
                  const testState = testingStatus[prov.id];
                  const currentVal = apiKeys[prov.id] ?? "";

                  return (
                    <div
                      key={prov.id}
                      className="rounded-xl bg-[#262624] border border-white/[0.07] p-4 space-y-3 flex flex-col justify-between"
                    >
                      <div className="space-y-1.5">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <ProviderIcon provider={prov.id} size={15} />
                            <span className="text-[14px] font-semibold text-zinc-100">
                              {prov.name}
                            </span>
                          </div>
                          <StatusBadge
                            tone={isConnected ? "success" : "neutral"}
                            label={isConnected ? "Siap digunakan" : "Belum diatur"}
                          />
                        </div>
                        <p className="text-xs text-zinc-300 leading-relaxed">{prov.desc}</p>
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
                              aria-label={`Kunci layanan ${prov.name}`}
                              placeholder={prov.placeholder}
                              autoComplete="off"
                              spellCheck={false}
                              className="w-full rounded-xl bg-[#191918] border border-white/[0.1] pl-3 pr-8 py-2 text-xs text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:border-[#D97757]"
                            />
                            <button
                              type="button"
                              onClick={() =>
                                setShowKeys((prev) => ({
                                  ...prev,
                                  [prov.id]: !prev[prov.id],
                                }))
                              }
                              title={showKeys[prov.id] ? "Sembunyikan" : "Tampilkan"}
                              className="absolute right-2 text-zinc-400 hover:text-zinc-200 p-0.5"
                            >
                              {showKeys[prov.id] ? <EyeOff size={14} /> : <Eye size={14} />}
                            </button>
                          </div>
                          <button
                            type="button"
                            onClick={() => void handleSaveKey(prov.id)}
                            disabled={isSavingKey === prov.id}
                            className="rounded-xl bg-[#D97757] hover:bg-[#c96a4b] px-3.5 py-2 text-xs font-semibold text-white transition-colors shrink-0"
                          >
                            {isSavingKey === prov.id ? "Menyimpan..." : "Simpan"}
                          </button>
                          <button
                            type="button"
                            onClick={() => void handleTestKey(prov.id, prov.defaultTestModel)}
                            disabled={testState?.loading}
                            className="rounded-xl bg-white/[0.06] hover:bg-white/[0.12] border border-white/[0.1] px-3 py-2 text-xs font-medium text-zinc-200 transition-colors flex items-center gap-1 shrink-0"
                          >
                            <Play size={11} className={testState?.loading ? "animate-spin" : ""} />
                            <span>Uji</span>
                          </button>
                        </div>

                        {testState && !testState.loading && (
                          <div
                            className={`rounded-xl p-2.5 text-xs flex items-start gap-2 ${
                              testState.ok
                                ? "bg-emerald-500/10 text-emerald-200 border border-emerald-500/25"
                                : "bg-rose-500/10 text-rose-200 border border-rose-500/25"
                            }`}
                          >
                            {testState.ok ? (
                              <CheckCircle2 size={14} className="shrink-0 mt-0.5 text-emerald-400" />
                            ) : (
                              <AlertCircle size={14} className="shrink-0 mt-0.5 text-rose-400" />
                            )}
                            <span>{testState.message}</span>
                          </div>
                        )}

                        <div className="flex items-center justify-between text-xs text-zinc-400">
                          <span>Model: {prov.defaultTestModel}</span>
                          <a
                            href={prov.link}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-1 text-zinc-300 hover:text-white transition-colors"
                          >
                            <span>Dapatkan Kunci</span>
                            <ExternalLink size={11} />
                          </a>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Recommended Model Catalog */}
            <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 md:p-6 space-y-4">
              <SectionHeader
                icon={<Layers size={18} className="text-emerald-400" />}
                title="Daftar Model AI Siap Pakai"
                description="Seluruh model di bawah ini sudah tersedia di menu Tim AI tanpa perlu pengaturan tambahan."
              />

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
                {PRELOADED_MODELS.map((m) => (
                  <div
                    key={`${m.provider}_${m.model_id}`}
                    className="rounded-xl bg-[#262624] border border-white/[0.07] p-3.5 space-y-2"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-1.5 min-w-0">
                        <ProviderIcon provider={m.provider} size={14} />
                        <span className="text-[13px] font-semibold text-zinc-100 truncate">
                          {m.name}
                        </span>
                      </div>
                    </div>
                    <span className="inline-block rounded bg-[#D97757]/15 border border-[#D97757]/30 px-2 py-0.5 text-[11px] font-medium text-[#F09373]">
                      {m.badge_label}
                    </span>
                    <p className="text-xs text-zinc-300 leading-relaxed">{m.description}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* 4. PRIVASI DAN DATA */}
        {activeCategory === "privasi_data" && (
          <div className="space-y-4">
            <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 md:p-6 space-y-4">
              <SectionHeader
                icon={<Shield size={18} className="text-emerald-400" />}
                title="Privasi & Perlindungan Data"
                description="Atur bagaimana AKSA melindungi dokumen sensitif, data pribadi, dan kredensial di komputer Anda."
              />

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
                {[
                  {
                    id: "local_first" as const,
                    title: "Utamakan Pemrosesan Lokal",
                    desc: "Mengutamakan model AI lokal untuk dokumen internal dan meminta persetujuan untuk data sensitif.",
                  },
                  {
                    id: "strict_local" as const,
                    title: "Hanya Lokal (Offline Penuh)",
                    desc: "Memblokir seluruh pengiriman data ke layanan Cloud. Hanya menggunakan AI lokal di komputer Anda.",
                  },
                  {
                    id: "cloud_allowed" as const,
                    title: "Izinkan Model Cloud Terpilih",
                    desc: "Menggunakan model AI Cloud yang Anda pilih dengan pemindaian informasi sensitif otomatis.",
                  },
                ].map((opt) => (
                  <button
                    type="button"
                    key={opt.id}
                    onClick={() => setPrivacyMode(opt.id)}
                    className={`rounded-xl p-4 border text-left space-y-2 transition-all ${
                      privacyMode === opt.id
                        ? "bg-[#262624] border-[#D97757] ring-1 ring-[#D97757]/30"
                        : "bg-[#262624]/60 border-white/[0.07] hover:border-white/[0.16]"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-[14px] font-semibold text-zinc-100">{opt.title}</span>
                      {privacyMode === opt.id && (
                        <CheckCircle2 size={15} className="text-[#D97757]" />
                      )}
                    </div>
                    <p className="text-xs text-zinc-300 leading-relaxed">{opt.desc}</p>
                  </button>
                ))}
              </div>

              <div className="rounded-xl bg-[#262624] border border-white/[0.07] p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="space-y-1">
                  <div className="text-[14px] font-semibold text-zinc-100">
                    Pengaturan Hak Akses Komputer &amp; Folder
                  </div>
                  <p className="text-xs text-zinc-300">
                    Untuk mengatur atau mencabut izin akses folder, aplikasi, dan layar secara
                    mendetail, buka halaman Pusat Akses AKSA.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setActiveNav("izin_pc")}
                  className="rounded-xl bg-[#D97757] hover:bg-[#c96a4b] px-4 py-2 text-xs font-semibold text-white transition-colors shrink-0"
                >
                  Buka Pusat Akses AKSA
                </button>
              </div>
            </div>
          </div>
        )}

        {/* 5. PENYIMPANAN */}
        {activeCategory === "penyimpanan" && (
          <div className="space-y-6">
            <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 md:p-6 space-y-4">
              <SectionHeader
                icon={<FolderPlus size={18} className="text-[#D97757]" />}
                title="Tambah Folder Ruang Kerja"
                description="Tentukan folder di komputer Anda tempat AKSA membaca dokumen dan menyimpan hasil pekerjaan."
              />

              {folderNotice && (
                <div className="rounded-xl bg-emerald-500/10 border border-emerald-500/25 p-3 text-xs text-emerald-200 flex items-center gap-2">
                  <CheckCircle2 size={15} className="text-emerald-400" />
                  <span>{folderNotice}</span>
                </div>
              )}

              <form onSubmit={handleAddWorkspace} className="space-y-3">
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div className="sm:col-span-2 space-y-1">
                    <label
                      htmlFor="aksa-new-folder-path"
                      className="text-xs font-medium text-zinc-300"
                    >
                      Lokasi Folder di Komputer Anda
                    </label>
                    <input
                      id="aksa-new-folder-path"
                      type="text"
                      value={newFolderPath}
                      onChange={(e) => setNewFolderPath(e.target.value)}
                      placeholder="Contoh: /Users/nama/Documents/Laporan atau C:\Proyek\Data"
                      className="w-full rounded-xl bg-[#262624] border border-white/[0.1] px-3.5 py-2.5 text-[13px] text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:border-[#D97757]"
                    />
                  </div>
                  <div className="space-y-1">
                    <label
                      htmlFor="aksa-new-folder-name"
                      className="text-xs font-medium text-zinc-300"
                    >
                      Nama Singkat Folder (Opsional)
                    </label>
                    <input
                      id="aksa-new-folder-name"
                      type="text"
                      value={newFolderName}
                      onChange={(e) => setNewFolderName(e.target.value)}
                      placeholder="Contoh: Laporan Keuangan 2026"
                      className="w-full rounded-xl bg-[#262624] border border-white/[0.1] px-3.5 py-2.5 text-[13px] text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:border-[#D97757]"
                    />
                  </div>
                </div>

                <div className="flex justify-end">
                  <button
                    type="submit"
                    disabled={!newFolderPath.trim()}
                    className="rounded-xl bg-[#D97757] hover:bg-[#c96a4b] disabled:opacity-40 text-white px-4 py-2 text-[13px] font-semibold transition-colors flex items-center gap-1.5"
                  >
                    <Plus size={15} />
                    <span>Tambahkan Folder Ruang Kerja</span>
                  </button>
                </div>
              </form>
            </div>

            <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 md:p-6 space-y-4">
              <SectionHeader
                icon={<FolderOpen size={18} className="text-emerald-400" />}
                title={`Daftar Folder Ruang Kerja (${workspaces.length})`}
                description="Pilih folder aktif atau hapus folder dari daftar ruang kerja AKSA."
              />

              <div className="space-y-3">
                {workspaces.map((ws) => {
                  const isActive = ws.id === activeWorkspaceId;
                  return (
                    <div
                      key={ws.id}
                      className={`rounded-xl p-4 border flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${
                        isActive
                          ? "bg-[#262624] border-emerald-500/40"
                          : "bg-[#262624]/60 border-white/[0.07]"
                      }`}
                    >
                      <div className="space-y-0.5">
                        <div className="flex items-center gap-2">
                          <span className="text-[14px] font-semibold text-zinc-100">
                            {ws.name}
                          </span>
                          {isActive && <StatusBadge tone="success" label="Folder Aktif" />}
                        </div>
                        <div className="text-xs font-mono text-zinc-400 break-all">
                          {ws.folder_path}
                        </div>
                      </div>

                      <div className="flex items-center gap-2 shrink-0">
                        {!isActive && (
                          <button
                            type="button"
                            onClick={() => setActiveWorkspace(ws.id)}
                            className="rounded-xl bg-white/[0.07] hover:bg-emerald-600 hover:text-white px-3.5 py-1.5 text-xs font-semibold text-zinc-200 transition-colors"
                          >
                            Jadikan Aktif
                          </button>
                        )}
                        {workspaces.length > 1 && (
                          <button
                            type="button"
                            onClick={() => removeWorkspaceFolder(ws.id)}
                            title="Hapus folder ini dari daftar"
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
            </div>
          </div>
        )}

        {/* 6. JARINGAN */}
        {activeCategory === "jaringan" && (
          <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 md:p-6 space-y-4">
            <SectionHeader
              icon={<Globe size={18} className="text-sky-400" />}
              title="Status Jaringan & Layanan"
              description="Status komunikasi antara aplikasi AKSA, layanan AI lokal, dan integrasi eksternal."
            />

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="rounded-xl bg-[#262624] border border-white/[0.07] p-4 space-y-2">
                <div className="text-[14px] font-semibold text-zinc-100">Mesin Utama AKSA</div>
                <p className="text-xs text-zinc-300">
                  Berjalan secara lokal di perangkat ini dengan otentikasi sesi terlindungi.
                </p>
                <StatusBadge
                  tone={engineHealth.online ? "success" : "warning"}
                  label={engineHealth.online ? "Terhubung" : "Mode Mandiri"}
                />
              </div>

              <div className="rounded-xl bg-[#262624] border border-white/[0.07] p-4 space-y-2">
                <div className="text-[14px] font-semibold text-zinc-100">Server AI Lokal (Ollama)</div>
                <p className="text-xs text-zinc-300">
                  Alamat lokal standar <code>127.0.0.1:11434</code> tanpa lalu lintas internet luar.
                </p>
                <StatusBadge
                  tone={engineHealth.ollama_online ? "success" : "neutral"}
                  label={engineHealth.ollama_online ? "Aktif" : "Tidak aktif"}
                />
              </div>

              <div className="rounded-xl bg-[#262624] border border-white/[0.07] p-4 space-y-2">
                <div className="text-[14px] font-semibold text-zinc-100">Integrasi Telegram</div>
                <p className="text-xs text-zinc-300">
                  Menggunakan koneksi aman tanpa membuka port masuk pada jaringan rumah/kantor Anda.
                </p>
                <StatusBadge
                  tone={engineHealth.telegram_connected ? "success" : "neutral"}
                  label={engineHealth.telegram_connected ? "Terhubung" : "Belum diatur"}
                />
              </div>
            </div>
          </div>
        )}

        {/* 7. LANJUTAN */}
        {activeCategory === "lanjutan" && (
          <div className="space-y-6">
            {/* Custom Model Registration */}
            <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 md:p-6 space-y-4">
              <SectionHeader
                icon={<Sliders size={18} className="text-sky-400" />}
                title="Daftarkan Model Kustom (Mode Lanjutan)"
                description="Tambahkan nama model baru atau model khusus dari penyedia AI Anda."
              />

              {customModelSuccess && (
                <div className="rounded-xl bg-emerald-500/10 border border-emerald-500/25 p-3 text-xs text-emerald-200 flex items-center gap-2">
                  <CheckCircle2 size={15} className="text-emerald-400" />
                  <span>{customModelSuccess}</span>
                </div>
              )}

              <form onSubmit={handleAddCustomModel} className="flex flex-col sm:flex-row gap-3">
                <select
                  aria-label="Pilih Penyedia AI"
                  value={customProvider}
                  onChange={(e) => setCustomProvider(e.target.value as ModelProvider)}
                  className="rounded-xl bg-[#262624] border border-white/[0.1] px-3.5 py-2.5 text-[13px] text-zinc-100 focus:outline-none focus:border-[#D97757]"
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
                  className="flex-1 rounded-xl bg-[#262624] border border-white/[0.1] px-3.5 py-2.5 text-[13px] text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:border-[#D97757]"
                />

                <button
                  type="submit"
                  disabled={!customModelId.trim()}
                  className="rounded-xl bg-[#D97757] hover:bg-[#c96a4b] disabled:opacity-40 text-white px-4 py-2.5 text-[13px] font-semibold transition-colors flex items-center justify-center gap-1.5 shrink-0"
                >
                  <Plus size={15} />
                  <span>Daftarkan Model Kustom</span>
                </button>
              </form>
            </div>

            {/* Token Efficiency Analytics */}
            <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 md:p-6 space-y-4">
              <SectionHeader
                icon={<Zap size={18} className="text-amber-400" />}
                title="Statistik Efisiensi Pemakaian Kuota (Token)"
                description="Ringkasan penghematan kuota AI melalui pemisahan tugas agen pendukung."
              />

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="rounded-xl bg-[#262624] border border-white/[0.07] p-4 space-y-1">
                  <span className="text-xs text-zinc-400">Rasio Penghematan</span>
                  <div className="text-2xl font-bold text-emerald-400">
                    {hasTokenActivity ? `${savingsPct}% Hemat` : "0%"}
                  </div>
                </div>
                <div className="rounded-xl bg-[#262624] border border-white/[0.07] p-4 space-y-1">
                  <span className="text-xs text-zinc-400">Total Token Dihemat</span>
                  <div className="text-2xl font-bold text-zinc-100">
                    {formatNumberID(totalTokensSaved)} Token
                  </div>
                </div>
                <div className="rounded-xl bg-[#262624] border border-white/[0.07] p-4 space-y-1">
                  <span className="text-xs text-zinc-400">Token Koordinator Utama</span>
                  <div className="text-2xl font-bold text-zinc-100">
                    {formatNumberID(totalTokensUsed)} Token
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 8. INFORMASI APLIKASI */}
        {activeCategory === "info_aplikasi" && (
          <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 md:p-6 space-y-4">
            <SectionHeader
              icon={<Info size={18} className="text-[#D97757]" />}
              title="Informasi Aplikasi AKSA"
              description="Rincian versi aplikasi desktop, mesin asisten, dan prinsip keamanan."
            />

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-[13.5px]">
              <div className="rounded-xl bg-[#262624] border border-white/[0.07] p-4 space-y-2">
                <div className="flex justify-between">
                  <span className="text-zinc-400">Nama Aplikasi:</span>
                  <span className="font-semibold text-zinc-100">AKSA Desktop AI Agent</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-400">Versi Mesin:</span>
                  <span className="font-mono text-zinc-200">v{engineHealth.version || "1.0.0"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-400">Ruang Kerja Aktif:</span>
                  <span className="text-zinc-200 truncate max-w-[200px]">
                    {activeWorkspace?.name || "Belum dipilih"}
                  </span>
                </div>
              </div>

              <div className="rounded-xl bg-[#262624] border border-white/[0.07] p-4 space-y-1.5">
                <div className="font-semibold text-zinc-100">Prinsip Utama AKSA</div>
                <p className="text-xs text-zinc-300 leading-relaxed">
                  Kompleksitas teknis berada di dalam mesin AKSA, bukan dibebankan kepada Anda.
                  Seluruh akses file dan aplikasi berada di bawah kendali serta persetujuan Anda.
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
