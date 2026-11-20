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
  Moon,
  Sun,
  Monitor,
  Edit3,
  RotateCcw,
  ChevronDown,
  ChevronRight,
  Lock,
} from "lucide-react";
import { toast } from "sonner";
import { useAksaStore } from "@/stores/useAksaStore";
import {
  saveProviderApiKey,
  saveSystemSettingRemote,
  deleteProviderApiKeyRemote,
  fetchProviderDetails,
  testModelConnectionRemote,
  openNativeFolderPicker,
  inspectWorkspacePathRemote,
  openFileInDefaultApp,
  fetchRootDirStatusRemote,
  setRootDirRemote,
  updatePrivacySettingsRemote,
} from "@/services/engineClient";
import {
  cn,
  extractFolderDisplayName,
  formatNumberID,
  formatProviderTokenStatus,
  formatWorkspaceFolderStatus,
} from "@/lib/utils";
import { ProviderIcon } from "@/components/ui/DynamicIcon";
import {
  ConfirmDialog,
  PageHeader,
  SectionHeader,
  StatusBadge,
} from "@/components/ui/UXPrimitives";
import type {
  ModelProvider,
  ProviderStatusDetail,
  ProviderTokenStatus,
  ThemeMode,
  WorkspaceFolder,
  WorkspaceFolderInspection,
} from "@/types/aksa";
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
}

const PRELOADED_MODELS: PreloadedModel[] = [
  {
    provider: "gemini",
    model_id: "gemini-4-carbon",
    name: "Gemini 4 Carbon",
    badge_label: "Koordinasi & Penalaran",
    description: "Model utama Google Gemini 4 untuk koordinasi tim AI dan analisis mendalam.",
  },
  {
    provider: "gemini",
    model_id: "gemini-4-argon",
    name: "Gemini 4 Argon",
    badge_label: "Multimodal & Dokumen",
    description: "Model unggulan Gemini 4 untuk pemrosesan dokumen panjang dan tugas kompleks.",
  },
  {
    provider: "gemini",
    model_id: "gemini-3.8-flash",
    name: "Gemini 3.8 Flash",
    badge_label: "Cepat & Tangkas",
    description: "Model harian berkecepatan tinggi untuk respons cepat.",
  },
  {
    provider: "anthropic",
    model_id: "claude-opus-5-5",
    name: "Claude Opus 5.5",
    badge_label: "Penulisan & Telaah",
    description: "Model utama Claude 5.5 untuk telaah dokumen dan penulisan laporan.",
  },
  {
    provider: "anthropic",
    model_id: "claude-sonnet-5-5",
    name: "Claude Sonnet 5.5",
    badge_label: "Agen & Aplikasi",
    description: "Kombinasi kecepatan dan ketepatan terbaik untuk pengolahan dokumen & aplikasi.",
  },
  {
    provider: "openai",
    model_id: "gpt-6.2-astra",
    name: "GPT-6.2 Astra",
    badge_label: "Penalaran Lanjut",
    description: "Model unggulan OpenAI generasi GPT-6.2 untuk analisis dan sintesis.",
  },
  {
    provider: "deepseek",
    model_id: "deepseek-v4-pro",
    name: "DeepSeek V4 Pro",
    badge_label: "Analisis Data & Excel",
    description: "Sangat akurat dan hemat kuota untuk pemodelan tabel Excel serta analisis angka.",
  },
  {
    provider: "ollama",
    model_id: "qwen3.8:8b",
    name: "Qwen 3.8 8B (Ollama Lokal)",
    badge_label: "Rekomendasi Lokal Gratis",
    description: "Berjalan langsung di komputer Anda tanpa internet dan tanpa biaya kuota API.",
  },
];

const CLOUD_PROVIDERS: {
  id: ModelProvider;
  name: string;
  desc: string;
  exampleFormat: string;
  link: string;
  defaultTestModel: string;
}[] = [
  {
    id: "gemini",
    name: "Google Gemini",
    desc: "Gemini 4 Carbon, 4 Argon & 3.8 Flash",
    exampleFormat: "Contoh format: AIza... (tempel token baru)",
    link: "https://aistudio.google.com/app/apikey",
    defaultTestModel: "gemini-3.8-flash",
  },
  {
    id: "anthropic",
    name: "Anthropic Claude",
    desc: "Claude Fable 5.2, Opus 5.5 & Sonnet 5.5",
    exampleFormat: "Contoh format: sk-ant-... (tempel token baru)",
    link: "https://console.anthropic.com/",
    defaultTestModel: "claude-sonnet-5-5",
  },
  {
    id: "deepseek",
    name: "DeepSeek",
    desc: "DeepSeek V4 Pro, V4.1 Flash & R1",
    exampleFormat: "Contoh format: sk-... (tempel token baru)",
    link: "https://platform.deepseek.com/",
    defaultTestModel: "deepseek-flash",
  },
  {
    id: "openai",
    name: "OpenAI",
    desc: "GPT-6.2 Astra, GPT-6.2 Sol & GPT-6 Luna",
    exampleFormat: "Contoh format: sk-proj-... (tempel token baru)",
    link: "https://platform.openai.com/api-keys",
    defaultTestModel: "gpt-6.2-sol",
  },
  {
    id: "groq",
    name: "Groq Cloud",
    desc: "Llama 4 Maverick & Qwen 3.8",
    exampleFormat: "Contoh format: gsk_... (tempel token baru)",
    link: "https://console.groq.com/keys",
    defaultTestModel: "meta-llama/llama-4-scout-17b-16e-instruct",
  },
  {
    id: "openrouter",
    name: "OpenRouter",
    desc: "Satu token untuk berbagai model AI",
    exampleFormat: "Contoh format: sk-or-... (tempel token baru)",
    link: "https://openrouter.ai/keys",
    defaultTestModel: "openrouter/auto",
  },
];

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
  { id: "umum", label: "Umum", icon: Settings },
  { id: "tampilan", label: "Tampilan", icon: Palette },
  { id: "model_ai", label: "AI & Model", icon: Cpu },
  { id: "penyimpanan", label: "Ruang Kerja", icon: HardDrive },
  { id: "privasi_data", label: "Privasi & Data", icon: Shield },
  { id: "jaringan", label: "Jaringan", icon: Globe },
  { id: "lanjutan", label: "Lanjutan", icon: Wrench },
  { id: "info_aplikasi", label: "Informasi Aplikasi", icon: Info },
];

export const FeatureSectionsView: React.FC = () => {
  const {
    activeNav,
    themeMode,
    resolvedTheme,
    uiDensity,
    reducedMotion,
    setThemeMode,
    setUiDensity,
    setReducedMotion,
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

  const [activeCategory, setActiveCategory] = useState<SettingsCategory>("tampilan");
  const [privacyMode, setPrivacyMode] = useState<"local_first" | "strict_local" | "cloud_allowed">(
    "local_first"
  );

  // API Token State (NEVER stores or pre-fills existing secrets in draftKeys!)
  const [draftKeys, setDraftKeys] = useState<Record<string, string>>({});
  const [editingTokenProvider, setEditingTokenProvider] = useState<Record<string, boolean>>({});
  const [providerMap, setProviderMap] = useState<Record<string, ProviderStatusDetail>>({});
  const [maskedHints, setMaskedHints] = useState<Record<string, string>>({});
  const [savedNotice, setSavedNotice] = useState<string | null>(null);
  const [isSavingKey, setIsSavingKey] = useState<string | null>(null);
  const [showDraftKey, setShowDraftKey] = useState<Record<string, boolean>>({});
  const [providerPendingDeleteToken, setProviderPendingDeleteToken] = useState<string | null>(null);
  const [testingStatus, setTestingStatus] = useState<
    Record<
      string,
      {
        loading: boolean;
        ok?: boolean;
        status?: ProviderTokenStatus;
        message?: string;
        technicalDetail?: string;
        showTech?: boolean;
      }
    >
  >({});

  // Custom Model Form State
  const [customProvider, setCustomProvider] = useState<ModelProvider>("gemini");
  const [customModelId, setCustomModelId] = useState("");
  const [customModelSuccess, setCustomModelSuccess] = useState<string | null>(null);

  // Workspace Folder Picker & Confirmation State (Section 6)
  const [manualFolderInputOpen, setManualFolderInputOpen] = useState(false);
  const [newFolderPath, setNewFolderPath] = useState("");
  const [newFolderName, setNewFolderName] = useState("");
  const [folderNotice, setFolderNotice] = useState<string | null>(null);
  const [copiedPathId, setCopiedPathId] = useState<string | null>(null);
  const [pendingFolderConfirm, setPendingFolderConfirm] = useState<{
    folderPath: string;
    displayName: string;
    inspection: WorkspaceFolderInspection | null;
    allowRead: boolean;
    allowWrite: boolean;
    replacingWorkspace?: WorkspaceFolder | null;
  } | null>(null);
  const [rootDirInfo, setRootDirInfo] = useState<{
    root_path?: string;
    default_path?: string;
    is_custom?: boolean;
  } | null>(null);
  const [confirmResetThemeOpen, setConfirmResetThemeOpen] = useState(false);

  // Local AI State
  const [isCheckingOllama, setIsCheckingOllama] = useState(false);
  const [copiedCmd, setCopiedCmd] = useState(false);

  const activeWorkspace = workspaces.find((w) => w.id === activeWorkspaceId) ?? workspaces[0];

  const loadProviderStatus = async () => {
    const details = await fetchProviderDetails();
    if (details) {
      setMaskedHints(details.maskedHints);
      const pMap: Record<string, ProviderStatusDetail> = {};
      for (const p of details.providers) {
        pMap[p.id] = p;
      }
      setProviderMap(pMap);
    }
  };

  const loadRootDirStatus = async () => {
    const info = await fetchRootDirStatusRemote();
    if (info) {
      setRootDirInfo(info);
    }
  };

  useEffect(() => {
    void loadProviderStatus();
    void loadRootDirStatus();
  }, []);

  if (activeNav === "pengetahuan_rag") return <KnowledgeBaseView />;
  if (activeNav === "telegram") return <TelegramGatewayView />;
  if (activeNav === "aplikasi") return <ApplicationsView />;
  if (activeNav === "keahlian") return <SkillsView />;
  if (activeNav === "izin_pc") return <PermissionsAndPCView />;

  const getEffectiveProviderTokenStatus = (provId: string): ProviderTokenStatus => {
    const testState = testingStatus[provId];
    if (testState && !testState.loading && testState.status) {
      return testState.status;
    }
    const pDetail = providerMap[provId];
    if (!pDetail) return "not_connected";
    if (!pDetail.has_saved_token) return "not_connected";
    return pDetail.token_status || "token_saved";
  };

  const handleSaveKey = async (provider: string) => {
    const rawDraft = draftKeys[provider]?.trim() ?? "";
    if (!rawDraft) {
      toast.error("Masukkan token API baru terlebih dahulu sebelum menyimpan.");
      return;
    }
    setIsSavingKey(provider);
    let ok = false;
    try {
      ok = await saveProviderApiKey(provider, rawDraft);
    } finally {
      setIsSavingKey(null);
    }

    if (ok) {
      // Clear draft input immediately so raw token never lingers in component state
      setDraftKeys((prev) => ({ ...prev, [provider]: "" }));
      setShowDraftKey((prev) => ({ ...prev, [provider]: false }));
      setEditingTokenProvider((prev) => ({ ...prev, [provider]: false }));
      await loadProviderStatus();
      setSavedNotice(
        `Token layanan ${provider.toUpperCase()} berhasil disimpan di brankas keamanan perangkat. Memverifikasi koneksi...`
      );
      const provMeta = CLOUD_PROVIDERS.find((p) => p.id === provider);
      if (provMeta) {
        await handleTestKey(provMeta.id, provMeta.defaultTestModel);
      }
      setTimeout(() => setSavedNotice(null), 4000);
    } else {
      toast.error(
        "Gagal menyimpan token baru. Token lama yang sudah tersimpan tetap aman dan tidak dihapus."
      );
    }
  };

  const handleConfirmDeleteToken = async () => {
    if (!providerPendingDeleteToken) return;
    const prov = providerPendingDeleteToken;
    setProviderPendingDeleteToken(null);
    const ok = await deleteProviderApiKeyRemote(prov);
    if (ok) {
      setDraftKeys((prev) => ({ ...prev, [prov]: "" }));
      setEditingTokenProvider((prev) => ({ ...prev, [prov]: false }));
      setTestingStatus((prev) => {
        const next = { ...prev };
        delete next[prov];
        return next;
      });
      await loadProviderStatus();
      toast.success(`Token API ${prov.toUpperCase()} telah dihapus dari perangkat.`);
    } else {
      toast.error("Gagal menghapus token API.");
    }
  };

  const handleTestKey = async (provider: ModelProvider, defaultModel: string) => {
    setTestingStatus((prev) => ({
      ...prev,
      [provider]: { loading: true },
    }));

    try {
      // If user typed a new draft token, save it first before testing
      const draft = draftKeys[provider]?.trim();
      if (draft && !draft.includes("••••")) {
        const saved = await saveProviderApiKey(provider, draft);
        if (saved) {
          setDraftKeys((prev) => ({ ...prev, [provider]: "" }));
          setShowDraftKey((prev) => ({ ...prev, [provider]: false }));
          setEditingTokenProvider((prev) => ({ ...prev, [provider]: false }));
          await loadProviderStatus();
        }
      }

      const res = await testModelConnectionRemote({
        provider,
        model_id: defaultModel,
      });
      await loadProviderStatus();

      if (res.ok) {
        setTestingStatus((prev) => ({
          ...prev,
          [provider]: {
            loading: false,
            ok: true,
            status: "connected",
            message: `Terhubung: Koneksi ke ${defaultModel} berhasil diverifikasi.`,
          },
        }));
      } else {
        setTestingStatus((prev) => ({
          ...prev,
          [provider]: {
            loading: false,
            ok: false,
            status: res.token_status || "connection_failed",
            message:
              res.error ||
              "Pemeriksaan koneksi gagal. Periksa apakah token API sudah benar dan kuota penyedia aktif.",
            technicalDetail: `Provider: ${provider} | Model uji: ${defaultModel} | Status: ${
              res.token_status || "connection_failed"
            }`,
          },
        }));
      }
    } catch (err: any) {
      setTestingStatus((prev) => ({
        ...prev,
        [provider]: {
          loading: false,
          ok: false,
          status: "connection_failed",
          message: err?.message || "Gagal menguji koneksi ke penyedia model.",
        },
      }));
    }
  };

  // Native OS Folder Picker Flow (Section 6)
  const prepareFolderSelection = async (
    rawPath: string,
    customLabel?: string,
    replacingWs?: WorkspaceFolder | null
  ) => {
    const trimmed = rawPath.trim();
    if (!trimmed) return;
    const inspection = await inspectWorkspacePathRemote(trimmed);
    const displayName =
      customLabel?.trim() ||
      inspection?.name ||
      extractFolderDisplayName(trimmed);

    setPendingFolderConfirm({
      folderPath: inspection?.folder_path || trimmed,
      displayName,
      inspection,
      allowRead: true,
      allowWrite: inspection ? inspection.writable : true,
      replacingWorkspace: replacingWs ?? null,
    });
  };

  const handlePickNativeFolder = async (replacingWs?: WorkspaceFolder | null) => {
    const picked = await openNativeFolderPicker({
      title: replacingWs
        ? `Ganti Lokasi Folder "${replacingWs.name}"`
        : "Pilih Folder Ruang Kerja AKSA",
      defaultPath: replacingWs?.folder_path || activeWorkspace?.folder_path,
    });
    if (!picked) {
      // User cancelled native dialog — Section 6: "Tangani cancel tanpa mengubah pengaturan"
      return;
    }
    await prepareFolderSelection(picked, undefined, replacingWs);
  };

  const handleConfirmFolderSelection = async () => {
    if (!pendingFolderConfirm) return;
    const { folderPath, displayName, allowRead, allowWrite, replacingWorkspace, inspection } =
      pendingFolderConfirm;

    if (inspection && !inspection.is_valid_directory) {
      toast.error(
        inspection.recovery_hint || "Lokasi yang dipilih tidak dapat dijadikan folder kerja."
      );
      return;
    }

    if (replacingWorkspace && replacingWorkspace.folder_path !== folderPath) {
      await removeWorkspaceFolder(replacingWorkspace.id);
    }

    await addWorkspaceFolder(folderPath, displayName, {
      allow_read: allowRead,
      allow_write: allowWrite,
      allow_execute: false,
    });
    setPendingFolderConfirm(null);
    setManualFolderInputOpen(false);
    setNewFolderPath("");
    setNewFolderName("");
    setFolderNotice(
      `Folder "${displayName}" telah ditetapkan sebagai Ruang Kerja aktif dengan izin akses yang Anda pilih.`
    );
    setTimeout(() => setFolderNotice(null), 4500);
  };

  const handleResetDefaultRootDir = async () => {
    const defaultPath = rootDirInfo?.default_path;
    if (defaultPath) {
      const res = await setRootDirRemote(defaultPath);
      if (res) {
        await loadRootDirStatus();
        toast.success("Lokasi penyimpanan data AKSA dikembalikan ke folder default.");
        return;
      }
    }
    toast.success("Lokasi penyimpanan menggunakan folder standar aplikasi AKSA.");
  };

  const handleCopyPath = (id: string, path: string) => {
    void navigator.clipboard.writeText(path);
    setCopiedPathId(id);
    toast.success("Lokasi folder disalin ke papan klip.");
    setTimeout(() => setCopiedPathId(null), 2000);
  };

  const handleOpenFolderInOS = async (folderPath: string) => {
    const ok = await openFileInDefaultApp(folderPath);
    if (!ok) {
      toast.error(
        "Tidak dapat membuka folder di file manager. Pastikan folder terdaftar dan masih tersedia di komputer Anda."
      );
    }
  };

  const handleAddCustomModel = (e: React.FormEvent) => {
    e.preventDefault();
    const cleaned = customModelId.trim();
    if (!cleaned) return;
    void saveSystemSettingRemote(`custom_model_${customProvider}`, {
      provider: customProvider,
      model_id: cleaned,
    });
    setCustomModelSuccess(
      `Model kustom "${cleaned}" (${customProvider}) telah disimpan dan siap dipilih secara manual di halaman Tim AI.`
    );
    setCustomModelId("");
    setTimeout(() => setCustomModelSuccess(null), 4000);
  };

  const handleCopyOllamaCommand = () => {
    void navigator.clipboard.writeText("ollama run qwen3.8:8b");
    setCopiedCmd(true);
    setTimeout(() => setCopiedCmd(false), 2000);
  };

  const handleCheckOllamaAgain = async () => {
    setIsCheckingOllama(true);
    await syncWithBackendEngine();
    await loadProviderStatus();
    setTimeout(() => setIsCheckingOllama(false), 500);
  };

  const handleSelectPrivacyMode = async (
    mode: "local_first" | "strict_local" | "cloud_allowed"
  ) => {
    setPrivacyMode(mode);
    const backendMode =
      mode === "strict_local"
        ? "local_only"
        : mode === "local_first"
        ? "hybrid_with_consent"
        : "cloud_by_choice";
    await updatePrivacySettingsRemote({ provider_mode: backendMode });
    toast.success("Kebijakan privasi pemrosesan AI berhasil diperbarui.");
  };

  const hasTokenActivity = totalTokensUsed + totalTokensSaved > 0;
  const savingsPct = hasTokenActivity
    ? Math.round((totalTokensSaved / (totalTokensUsed + totalTokensSaved)) * 100)
    : 0;

  return (
    <div className="flex-1 p-6 md:p-8 overflow-y-auto bg-[#191918]">
      {/* 1. Confirm Delete API Token Modal (Section 5: Sediakan aksi Hapus token dengan konfirmasi) */}
      <ConfirmDialog
        open={providerPendingDeleteToken !== null}
        title={`Hapus token ${providerPendingDeleteToken?.toUpperCase() ?? ""}?`}
        description="Token yang tersimpan di brankas keamanan perangkat untuk penyedia ini akan dihapus secara permanen."
        impactNote="Agen yang menggunakan penyedia ini tidak akan dapat memanggil layanan Cloud tersebut hingga Anda menyimpan token baru atau memilih penyedia AI lain."
        confirmLabel="Ya, Hapus Token"
        cancelLabel="Batal"
        destructive
        onCancel={() => setProviderPendingDeleteToken(null)}
        onConfirm={() => void handleConfirmDeleteToken()}
      />

      {/* 2. Confirm Reset Appearance Settings Modal */}
      <ConfirmDialog
        open={confirmResetThemeOpen}
        title="Kembalikan pengaturan tampilan ke bawaan?"
        description="Tema akan dikembalikan ke Gelap, ukuran tampilan ke Nyaman, dan animasi ke Normal."
        confirmLabel="Kembalikan ke Bawaan"
        cancelLabel="Batal"
        onCancel={() => setConfirmResetThemeOpen(false)}
        onConfirm={() => {
          setThemeMode("dark");
          setUiDensity("comfortable");
          setReducedMotion(false);
          setConfirmResetThemeOpen(false);
          toast.success("Pengaturan tampilan dikembalikan ke bawaan.");
        }}
      />

      {/* 3. Confirm Workspace Folder Selection & Scoped Permissions Modal (Section 6) */}
      {pendingFolderConfirm && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="aksa-confirm-folder-title"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4"
        >
          <div className="w-full max-w-lg rounded-2xl bg-[#21211F] border border-white/[0.12] shadow-2xl p-6 space-y-4">
            <div className="space-y-1">
              <h3
                id="aksa-confirm-folder-title"
                className="text-[18px] font-semibold text-zinc-100"
              >
                {pendingFolderConfirm.replacingWorkspace
                  ? `Ganti Folder Ruang Kerja "${pendingFolderConfirm.replacingWorkspace.name}"?`
                  : "Konfirmasi Lokasi Folder Ruang Kerja"}
              </h3>
              <p className="text-[13px] text-zinc-300">
                Tinjau ringkasan lokasi folder dan tentukan izin akses yang Anda berikan.
              </p>
            </div>

            <div className="rounded-xl bg-[#262624] border border-white/[0.08] p-4 space-y-2.5 text-xs">
              <div className="flex items-center justify-between gap-2">
                <span className="text-zinc-400">Nama Folder:</span>
                <span className="text-[14px] font-semibold text-zinc-100">
                  {pendingFolderConfirm.displayName}
                </span>
              </div>
              <div className="space-y-0.5">
                <span className="text-zinc-400 block">Lokasi Lengkap:</span>
                <code className="block rounded-lg bg-[#191918] border border-white/[0.07] px-2.5 py-1.5 font-mono text-zinc-200 break-all">
                  {pendingFolderConfirm.folderPath}
                </code>
              </div>
              {pendingFolderConfirm.inspection && (
                <div className="flex items-center justify-between gap-2 pt-1">
                  <span className="text-zinc-400">Status Folder:</span>
                  <StatusBadge
                    tone={
                      formatWorkspaceFolderStatus(pendingFolderConfirm.inspection.folder_status)
                        .tone
                    }
                    label={
                      pendingFolderConfirm.inspection.folder_status_label ||
                      formatWorkspaceFolderStatus(pendingFolderConfirm.inspection.folder_status)
                        .label
                    }
                  />
                </div>
              )}
              {pendingFolderConfirm.inspection?.recovery_hint && (
                <p className="text-amber-300 pt-1 leading-relaxed">
                  {pendingFolderConfirm.inspection.recovery_hint}
                </p>
              )}
            </div>

            {/* Explicit Permission Choice (Section 6: Pemilihan folder tidak otomatis memberikan izin read/write/execute) */}
            <div className="rounded-xl bg-[#262624] border border-white/[0.08] p-4 space-y-2.5 text-xs">
              <div className="font-semibold text-zinc-100 text-[13px] flex items-center gap-1.5">
                <Lock size={13} className="text-[#D97757]" />
                <span>Izin Akses Folder Ini</span>
              </div>
              <p className="text-zinc-300 leading-relaxed">
                Memilih folder tidak otomatis memberikan izin penuh tanpa batas. Pilih izin dasar
                yang Anda setujui untuk folder ini:
              </p>

              <label className="flex items-center justify-between rounded-lg bg-[#191918] border border-white/[0.07] px-3 py-2 cursor-pointer">
                <span>Izinkan membaca dokumen di folder ini</span>
                <input
                  type="checkbox"
                  checked={pendingFolderConfirm.allowRead}
                  onChange={(e) =>
                    setPendingFolderConfirm((prev) =>
                      prev ? { ...prev, allowRead: e.target.checked } : null
                    )
                  }
                  className="accent-[#D97757]"
                />
              </label>

              <label className="flex items-center justify-between rounded-lg bg-[#191918] border border-white/[0.07] px-3 py-2 cursor-pointer">
                <span>Izinkan menyimpan hasil pekerjaan baru di folder ini</span>
                <input
                  type="checkbox"
                  checked={pendingFolderConfirm.allowWrite}
                  disabled={pendingFolderConfirm.inspection?.folder_status === "read_only"}
                  onChange={(e) =>
                    setPendingFolderConfirm((prev) =>
                      prev ? { ...prev, allowWrite: e.target.checked } : null
                    )
                  }
                  className="accent-[#D97757]"
                />
              </label>

              <p className="text-[11.5px] text-zinc-400">
                Catatan: Izin eksekusi program dan penghapusan file tetap dinonaktifkan secara
                default dan hanya dapat dilakukan dengan persetujuan Anda.
              </p>
            </div>

            <div className="flex items-center justify-end gap-2.5 pt-2">
              <button
                type="button"
                onClick={() => setPendingFolderConfirm(null)}
                className="rounded-xl bg-[#262624] hover:bg-zinc-700 border border-white/[0.1] px-4 py-2 text-[13px] font-medium text-zinc-200"
              >
                Batal
              </button>
              <button
                type="button"
                disabled={
                  pendingFolderConfirm.inspection !== null &&
                  !pendingFolderConfirm.inspection.is_valid_directory
                }
                onClick={() => void handleConfirmFolderSelection()}
                className="rounded-xl bg-[#D97757] hover:bg-[#c96a4b] disabled:opacity-40 px-4 py-2 text-[13px] font-semibold text-white"
              >
                Simpan Folder Ruang Kerja
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="max-w-6xl mx-auto space-y-6">
        <PageHeader
          icon={<Settings size={22} className="text-[#D97757]" />}
          title="Pengaturan AKSA"
          description="Atur tema tampilan, penyedia model AI & token API, folder ruang kerja, serta privasi data dengan mudah."
        />

        {savedNotice && (
          <div
            role="status"
            className="rounded-xl bg-emerald-500/10 border border-emerald-500/30 p-3.5 text-[13px] text-emerald-200 flex items-center gap-2"
          >
            <CheckCircle2 size={16} className="shrink-0 text-emerald-400" />
            <span>{savedNotice}</span>
          </div>
        )}

        {/* Structured Category Tabs */}
        <div
          role="tablist"
          aria-label="Kategori Pengaturan AKSA"
          className="flex flex-wrap items-center gap-2 border-b border-white/[0.07] pb-3"
        >
          {SETTINGS_CATEGORIES.map((cat) => {
            const Icon = cat.icon;
            const isActive = activeCategory === cat.id;
            return (
              <button
                type="button"
                role="tab"
                aria-selected={isActive}
                key={cat.id}
                onClick={() => setActiveCategory(cat.id)}
                className={cn(
                  "flex items-center gap-2 rounded-xl px-3.5 py-2 text-[13px] font-medium transition-all",
                  isActive
                    ? "bg-[#262624] text-zinc-100 border border-[#D97757]/50 shadow-sm"
                    : "text-zinc-300 hover:text-white hover:bg-white/[0.04]"
                )}
              >
                <Icon size={15} className={isActive ? "text-[#D97757]" : "text-zinc-400"} />
                <span>{cat.label}</span>
              </button>
            );
          })}
        </div>

        {/* =================================================================
            1. TAMPILAN — Tema Gelap / Terang / Ikuti Sistem (Section 2 & 7)
           ================================================================= */}
        {activeCategory === "tampilan" && (
          <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 md:p-6 space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <SectionHeader
                icon={<Palette size={18} className="text-[#D97757]" />}
                title="Pengaturan Tampilan & Tema"
                description="Pilih tema warna yang paling nyaman untuk mata Anda. Perubahan langsung diterapkan di seluruh aplikasi tanpa perlu memulai ulang."
              />
              <button
                type="button"
                onClick={() => setConfirmResetThemeOpen(true)}
                className="inline-flex items-center gap-1.5 rounded-xl bg-[#262624] hover:bg-zinc-700 border border-white/[0.08] px-3 py-1.5 text-xs font-medium text-zinc-300"
              >
                <RotateCcw size={13} />
                <span>Kembalikan Bawaan</span>
              </button>
            </div>

            {/* 3 Theme Option Cards with Mini Previews */}
            <div className="space-y-2">
              <label className="block text-[14px] font-semibold text-zinc-100">
                Tema Aplikasi
              </label>
              <div
                role="radiogroup"
                aria-label="Pilih tema warna aplikasi"
                className="grid grid-cols-1 md:grid-cols-3 gap-4"
              >
                {(
                  [
                    {
                      id: "dark" as ThemeMode,
                      title: "Gelap",
                      subtitle: "Tampilan khas AKSA (Default)",
                      desc: "Latar gelap hangat (#191918) dengan aksen oranye (#D97757) yang nyaman untuk kerja panjang.",
                      icon: Moon,
                      previewBg: "#191918",
                      previewCard: "#21211F",
                      previewText: "#ECECEB",
                    },
                    {
                      id: "light" as ThemeMode,
                      title: "Terang",
                      subtitle: "Kertas hangat beraksen AKSA",
                      desc: "Pasangan warna terang yang bersih dan kontras untuk ruangan bercahaya terang.",
                      icon: Sun,
                      previewBg: "#F6F4EF",
                      previewCard: "#FFFFFF",
                      previewText: "#1C1B18",
                    },
                    {
                      id: "system" as ThemeMode,
                      title: "Ikuti sistem",
                      subtitle: `Mengikuti OS (${resolvedTheme === "dark" ? "Gelap" : "Terang"} saat ini)`,
                      desc: "Menyesuaikan tema aplikasi secara otomatis mengikuti pengaturan gelap/terang perangkat Anda.",
                      icon: Monitor,
                      previewBg: "linear-gradient(135deg, #191918 50%, #F6F4EF 50%)",
                      previewCard: "#262624",
                      previewText: "#ECECEB",
                    },
                  ] as const
                ).map((item) => {
                  const Icon = item.icon;
                  const isSelected = themeMode === item.id;
                  return (
                    <button
                      type="button"
                      role="radio"
                      aria-checked={isSelected}
                      key={item.id}
                      onClick={() => setThemeMode(item.id)}
                      className={cn(
                        "rounded-2xl p-4 border text-left transition-all flex flex-col justify-between space-y-3",
                        isSelected
                          ? "bg-[#262624] border-[#D97757] ring-2 ring-[#D97757]/30"
                          : "bg-[#262624]/60 border-white/[0.08] hover:border-white/[0.2]"
                      )}
                    >
                      {/* Mini Theme Preview Swatch */}
                      <div
                        aria-hidden="true"
                        style={{ background: item.previewBg }}
                        className="h-16 w-full rounded-xl border border-black/20 p-2.5 flex items-center justify-between overflow-hidden"
                      >
                        <div
                          style={{ backgroundColor: item.previewCard }}
                          className="rounded-lg px-2.5 py-1.5 flex items-center gap-2 shadow-sm border border-white/10"
                        >
                          <span
                            style={{ backgroundColor: "#D97757" }}
                            className="h-2.5 w-2.5 rounded-full shrink-0"
                          />
                          <span
                            style={{ color: item.previewText }}
                            className="text-[11px] font-semibold"
                          >
                            AKSA {item.title}
                          </span>
                        </div>
                        {isSelected && (
                          <span className="rounded-full bg-[#D97757] text-white p-1">
                            <Check size={12} />
                          </span>
                        )}
                      </div>

                      <div className="space-y-1">
                        <div className="flex items-center justify-between">
                          <span className="inline-flex items-center gap-1.5 text-[15px] font-semibold text-zinc-100">
                            <Icon size={15} className="text-[#D97757]" />
                            <span>{item.title}</span>
                          </span>
                          {isSelected && <StatusBadge tone="accent" label="Aktif" />}
                        </div>
                        <div className="text-xs font-medium text-zinc-300">{item.subtitle}</div>
                        <p className="text-xs text-zinc-400 leading-relaxed">{item.desc}</p>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Density & Animation Controls */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2 border-t border-white/[0.07]">
              <div className="rounded-xl bg-[#262624] border border-white/[0.07] p-4 space-y-2.5">
                <div>
                  <div className="text-[14px] font-semibold text-zinc-100">
                    Ukuran Tampilan &amp; Kepadatan UI
                  </div>
                  <p className="text-xs text-zinc-300">
                    Sesuaikan jarak antar elemen dan ukuran teks sesuai ukuran layar Anda.
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setUiDensity("comfortable")}
                    className={cn(
                      "rounded-xl px-3.5 py-2 text-xs font-semibold border transition-colors",
                      uiDensity === "comfortable"
                        ? "bg-[#D97757] text-white border-[#D97757]"
                        : "bg-[#191918] text-zinc-300 border-white/10"
                    )}
                  >
                    Nyaman (Direkomendasikan)
                  </button>
                  <button
                    type="button"
                    onClick={() => setUiDensity("compact")}
                    className={cn(
                      "rounded-xl px-3.5 py-2 text-xs font-semibold border transition-colors",
                      uiDensity === "compact"
                        ? "bg-[#D97757] text-white border-[#D97757]"
                        : "bg-[#191918] text-zinc-300 border-white/10"
                    )}
                  >
                    Ringkas
                  </button>
                </div>
              </div>

              <div className="rounded-xl bg-[#262624] border border-white/[0.07] p-4 space-y-2.5">
                <div>
                  <div className="text-[14px] font-semibold text-zinc-100">Animasi Antarmuka</div>
                  <p className="text-xs text-zinc-300">
                    Kurangi efek animasi dan garis bergerak pada diagram jika Anda menyukai tampilan
                    statis.
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setReducedMotion(false)}
                    className={cn(
                      "rounded-xl px-3.5 py-2 text-xs font-semibold border transition-colors",
                      !reducedMotion
                        ? "bg-[#D97757] text-white border-[#D97757]"
                        : "bg-[#191918] text-zinc-300 border-white/10"
                    )}
                  >
                    Normal
                  </button>
                  <button
                    type="button"
                    onClick={() => setReducedMotion(true)}
                    className={cn(
                      "rounded-xl px-3.5 py-2 text-xs font-semibold border transition-colors",
                      reducedMotion
                        ? "bg-[#D97757] text-white border-[#D97757]"
                        : "bg-[#191918] text-zinc-300 border-white/10"
                    )}
                  >
                    Kurangi animasi
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* =================================================================
            2. AI & MODEL — Status Token 5-State, Masking Aman, Uji Koneksi (Section 5)
           ================================================================= */}
        {activeCategory === "model_ai" && (
          <div className="space-y-6">
            {/* Local AI (Ollama) */}
            <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 space-y-4">
              <div className="flex items-center justify-between">
                <SectionHeader
                  icon={<Cpu size={18} className="text-emerald-400" />}
                  title="Penyedia AI Lokal di Komputer Anda (Gratis & Tanpa Token)"
                  description="Gunakan Ollama atau LM Studio jika ingin menjalankan AI di perangkat sendiri tanpa memerlukan API token Cloud."
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
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-[14px] font-semibold text-zinc-100">Ollama Lokal</span>
                    <StatusBadge
                      tone={engineHealth.ollama_online ? "success" : "neutral"}
                      label={engineHealth.ollama_online ? "Terhubung" : "Belum dihubungkan"}
                    />
                  </div>
                  <p className="text-xs text-zinc-300">
                    {engineHealth.ollama_online && engineHealth.ollama_models.length > 0
                      ? `Model lokal siap pakai: ${engineHealth.ollama_models.join(", ")}`
                      : "Jalankan Ollama di komputer Anda jika ingin memakai model lokal gratis."}
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

            {/* Cloud AI Providers & Safe Token Management (Section 5) */}
            <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 md:p-6 space-y-5">
              <SectionHeader
                icon={<KeyRound size={18} className="text-[#D97757]" />}
                title="Penyedia AI Cloud & API Token"
                description="Token disimpan terenkripsi di brankas keamanan perangkat Anda. Demi keamanan, token yang sudah tersimpan tidak pernah dikirim kembali ke layar."
              />

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {CLOUD_PROVIDERS.map((prov) => {
                  const pDetail = providerMap[prov.id];
                  const hasSavedToken = Boolean(pDetail?.has_saved_token);
                  const effectiveStatus = getEffectiveProviderTokenStatus(prov.id);
                  const statusBadgeInfo = formatProviderTokenStatus(effectiveStatus, false);
                  const testState = testingStatus[prov.id];
                  const draftVal = draftKeys[prov.id] ?? "";
                  const isEditing = Boolean(editingTokenProvider[prov.id]) || !hasSavedToken;
                  const maskedHint = maskedHints[prov.id];

                  return (
                    <div
                      key={prov.id}
                      className="rounded-2xl bg-[#262624] border border-white/[0.08] p-4 space-y-3.5 flex flex-col justify-between"
                    >
                      {/* Card Header: Provider Name & 5-State Status Badge */}
                      <div className="space-y-1.5">
                        <div className="flex items-center justify-between gap-2 flex-wrap">
                          <div className="flex items-center gap-2">
                            <ProviderIcon provider={prov.id} size={16} />
                            <span className="text-[14.5px] font-semibold text-zinc-100">
                              {prov.name}
                            </span>
                          </div>
                          <StatusBadge
                            tone={statusBadgeInfo.tone}
                            label={statusBadgeInfo.label}
                          />
                        </div>
                        <p className="text-xs text-zinc-300 leading-relaxed">{prov.desc}</p>
                        <p className="text-[11.5px] text-zinc-400">{statusBadgeInfo.description}</p>
                      </div>

                      {/* Saved Token Indicator vs Input Area (Section 5 Perilaku input token) */}
                      <div className="space-y-2.5 pt-1">
                        {hasSavedToken && !editingTokenProvider[prov.id] ? (
                          <div className="rounded-xl bg-[#191918] border border-white/[0.08] px-3.5 py-2.5 flex flex-wrap items-center justify-between gap-2">
                            <div className="flex items-center gap-2 min-w-0">
                              <Lock size={13} className="shrink-0 text-emerald-400" />
                              <span className="text-xs font-medium text-emerald-300">
                                Token tersimpan
                              </span>
                              <span
                                aria-label={`Token ${prov.name} sudah tersimpan`}
                                className="font-mono text-xs text-zinc-400 tracking-wider select-none"
                              >
                                {maskedHint || "••••••••••••••••"}
                              </span>
                            </div>

                            <div className="flex items-center gap-1.5 shrink-0">
                              <button
                                type="button"
                                onClick={() =>
                                  setEditingTokenProvider((prev) => ({
                                    ...prev,
                                    [prov.id]: true,
                                  }))
                                }
                                className="inline-flex items-center gap-1 rounded-lg bg-white/[0.07] hover:bg-white/[0.13] border border-white/[0.09] px-2.5 py-1 text-xs font-medium text-zinc-200 transition-colors"
                              >
                                <Edit3 size={11} />
                                <span>Ganti token</span>
                              </button>
                              <button
                                type="button"
                                onClick={() => setProviderPendingDeleteToken(prov.id)}
                                title={`Hapus token ${prov.name}`}
                                className="inline-flex items-center gap-1 rounded-lg bg-rose-500/15 hover:bg-rose-500/25 border border-rose-500/30 px-2.5 py-1 text-xs font-medium text-rose-300 transition-colors"
                              >
                                <Trash2 size={11} />
                                <span>Hapus</span>
                              </button>
                            </div>
                          </div>
                        ) : (
                          <div className="space-y-2">
                            <label
                              htmlFor={`aksa-token-input-${prov.id}`}
                              className="block text-xs font-medium text-zinc-300"
                            >
                              {hasSavedToken
                                ? `Masukkan token baru untuk mengganti token ${prov.name}`
                                : `API Token ${prov.name}`}
                            </label>
                            <div className="flex items-center gap-2">
                              <div className="relative flex-1 flex items-center">
                                <input
                                  id={`aksa-token-input-${prov.id}`}
                                  type={showDraftKey[prov.id] ? "text" : "password"}
                                  value={draftVal}
                                  onChange={(e) =>
                                    setDraftKeys((prev) => ({
                                      ...prev,
                                      [prov.id]: e.target.value,
                                    }))
                                  }
                                  placeholder={
                                    hasSavedToken
                                      ? "Ketik token pengganti baru…"
                                      : prov.exampleFormat
                                  }
                                  autoComplete="off"
                                  spellCheck={false}
                                  className="w-full rounded-xl bg-[#191918] border border-white/[0.1] pl-3 pr-8 py-2 text-xs text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:border-[#D97757]"
                                />
                                {/* Eye button ONLY reveals new value currently being typed (Section 5) */}
                                {draftVal.length > 0 && (
                                  <button
                                    type="button"
                                    onClick={() =>
                                      setShowDraftKey((prev) => ({
                                        ...prev,
                                        [prov.id]: !prev[prov.id],
                                      }))
                                    }
                                    aria-label={
                                      showDraftKey[prov.id]
                                        ? "Sembunyikan token yang sedang diketik"
                                        : "Tampilkan token yang sedang diketik"
                                    }
                                    title={
                                      showDraftKey[prov.id]
                                        ? "Sembunyikan ketikan baru"
                                        : "Tampilkan ketikan baru"
                                    }
                                    className="absolute right-2 text-zinc-400 hover:text-zinc-200 p-0.5"
                                  >
                                    {showDraftKey[prov.id] ? (
                                      <EyeOff size={14} />
                                    ) : (
                                      <Eye size={14} />
                                    )}
                                  </button>
                                )}
                              </div>

                              <button
                                type="button"
                                onClick={() => void handleSaveKey(prov.id)}
                                disabled={isSavingKey === prov.id || !draftVal.trim()}
                                className="rounded-xl bg-[#D97757] hover:bg-[#c96a4b] disabled:opacity-40 px-3.5 py-2 text-xs font-semibold text-white transition-colors shrink-0"
                              >
                                {isSavingKey === prov.id
                                  ? "Menyimpan..."
                                  : hasSavedToken
                                  ? "Perbarui token"
                                  : "Simpan token"}
                              </button>

                              {hasSavedToken && isEditing && (
                                <button
                                  type="button"
                                  onClick={() => {
                                    setDraftKeys((prev) => ({ ...prev, [prov.id]: "" }));
                                    setShowDraftKey((prev) => ({ ...prev, [prov.id]: false }));
                                    setEditingTokenProvider((prev) => ({
                                      ...prev,
                                      [prov.id]: false,
                                    }));
                                  }}
                                  className="rounded-xl bg-white/[0.06] hover:bg-white/[0.12] border border-white/[0.1] px-2.5 py-2 text-xs text-zinc-300"
                                >
                                  Batal
                                </button>
                              )}
                            </div>
                          </div>
                        )}

                        {/* Action Bar: Uji Koneksi & Dapatkan API Key */}
                        <div className="flex items-center justify-between gap-2 pt-1">
                          <button
                            type="button"
                            onClick={() => void handleTestKey(prov.id, prov.defaultTestModel)}
                            disabled={testState?.loading || (!hasSavedToken && !draftVal.trim())}
                            className="rounded-xl bg-white/[0.06] hover:bg-white/[0.12] disabled:opacity-40 border border-white/[0.1] px-3 py-1.5 text-xs font-medium text-zinc-200 transition-colors inline-flex items-center gap-1.5"
                          >
                            <Play size={11} className={testState?.loading ? "animate-spin" : ""} />
                            <span>
                              {testState?.loading ? "Menguji koneksi..." : "Uji koneksi"}
                            </span>
                          </button>

                          <a
                            href={prov.link}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-1 text-xs text-zinc-300 hover:text-white transition-colors"
                          >
                            <span>Dapatkan API key</span>
                            <ExternalLink size={11} />
                          </a>
                        </div>

                        {/* Test Feedback with Safe Message & Collapsible Technical Detail */}
                        {testState && !testState.loading && (
                          <div
                            className={cn(
                              "rounded-xl p-2.5 text-xs space-y-1.5 border",
                              testState.ok
                                ? "bg-emerald-500/10 text-emerald-200 border-emerald-500/25"
                                : "bg-rose-500/10 text-rose-200 border-rose-500/25"
                            )}
                          >
                            <div className="flex items-start gap-2">
                              {testState.ok ? (
                                <CheckCircle2
                                  size={14}
                                  className="shrink-0 mt-0.5 text-emerald-400"
                                />
                              ) : (
                                <AlertCircle size={14} className="shrink-0 mt-0.5 text-rose-400" />
                              )}
                              <span>{testState.message}</span>
                            </div>

                            {!testState.ok && testState.technicalDetail && (
                              <div className="pl-5">
                                <button
                                  type="button"
                                  onClick={() =>
                                    setTestingStatus((prev) => ({
                                      ...prev,
                                      [prov.id]: {
                                        ...prev[prov.id],
                                        showTech: !prev[prov.id]?.showTech,
                                      },
                                    }))
                                  }
                                  className="inline-flex items-center gap-1 text-[11px] text-zinc-300 hover:underline"
                                >
                                  {testState.showTech ? (
                                    <ChevronDown size={11} />
                                  ) : (
                                    <ChevronRight size={11} />
                                  )}
                                  <span>Detail</span>
                                </button>
                                {testState.showTech && (
                                  <div className="mt-1 rounded bg-black/30 p-2 font-mono text-[10.5px] text-zinc-300">
                                    {testState.technicalDetail}
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Preloaded Models Reference */}
            <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 md:p-6 space-y-4">
              <SectionHeader
                icon={<Layers size={18} className="text-emerald-400" />}
                title="Daftar Model AI Siap Pakai"
                description="Model di bawah ini dapat dipilih secara otomatis maupun manual untuk setiap agen di halaman Tim AI."
              />

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
                {PRELOADED_MODELS.map((m) => (
                  <div
                    key={`${m.provider}_${m.model_id}`}
                    className="rounded-xl bg-[#262624] border border-white/[0.07] p-3.5 space-y-2"
                  >
                    <div className="flex items-center gap-1.5 min-w-0">
                      <ProviderIcon provider={m.provider} size={14} />
                      <span className="text-[13px] font-semibold text-zinc-100 truncate">
                        {m.name}
                      </span>
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

        {/* =================================================================
            3. RUANG KERJA & PENYIMPANAN — Native OS Folder Picker (Section 6)
           ================================================================= */}
        {activeCategory === "penyimpanan" && (
          <div className="space-y-6">
            {/* Active Workspace Primary Card with Native OS Picker */}
            <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 md:p-6 space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <SectionHeader
                  icon={<FolderOpen size={18} className="text-[#D97757]" />}
                  title="Folder Ruang Kerja Aktif"
                  description="Pilih folder di komputer Anda melalui file manager (Explorer / Finder) tanpa perlu mengetik alamat path teknis."
                />

                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => void handlePickNativeFolder(null)}
                    className="rounded-xl bg-[#D97757] hover:bg-[#c96a4b] px-4 py-2 text-[13px] font-semibold text-white flex items-center gap-2 transition-colors shadow-sm"
                  >
                    <FolderPlus size={15} />
                    <span>Pilih folder…</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setManualFolderInputOpen((v) => !v)}
                    className="rounded-xl bg-[#262624] hover:bg-zinc-700 border border-white/[0.1] px-3 py-2 text-xs font-medium text-zinc-200 transition-colors"
                  >
                    {manualFolderInputOpen ? "Tutup Input Path" : "Masukkan Lokasi Manual"}
                  </button>
                </div>
              </div>

              {folderNotice && (
                <div className="rounded-xl bg-emerald-500/10 border border-emerald-500/25 p-3 text-xs text-emerald-200 flex items-center gap-2">
                  <CheckCircle2 size={15} className="text-emerald-400 shrink-0" />
                  <span>{folderNotice}</span>
                </div>
              )}

              {/* Manual fallback form (progressive disclosure for users who want to paste a path or in browser test env) */}
              {manualFolderInputOpen && (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    void prepareFolderSelection(newFolderPath, newFolderName || undefined, null);
                  }}
                  className="rounded-xl bg-[#262624] border border-white/[0.09] p-4 space-y-3"
                >
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
                        placeholder="Tempel lokasi folder jika tidak menggunakan jendela Pilih folder…"
                        className="w-full rounded-xl bg-[#191918] border border-white/[0.1] px-3.5 py-2 text-[13px] text-zinc-100"
                      />
                    </div>
                    <div className="space-y-1">
                      <label
                        htmlFor="aksa-new-folder-name"
                        className="text-xs font-medium text-zinc-300"
                      >
                        Nama Tampilan Folder (Opsional)
                      </label>
                      <input
                        id="aksa-new-folder-name"
                        type="text"
                        value={newFolderName}
                        onChange={(e) => setNewFolderName(e.target.value)}
                        placeholder="Contoh: Laporan Keuangan 2026"
                        className="w-full rounded-xl bg-[#191918] border border-white/[0.1] px-3.5 py-2 text-[13px] text-zinc-100"
                      />
                    </div>
                  </div>
                  <div className="flex justify-end">
                    <button
                      type="submit"
                      disabled={!newFolderPath.trim()}
                      className="rounded-xl bg-[#D97757] hover:bg-[#c96a4b] disabled:opacity-40 text-white px-4 py-2 text-xs font-semibold"
                    >
                      Periksa &amp; Tambahkan Folder
                    </button>
                  </div>
                </form>
              )}

              {/* Workspace Folder Cards */}
              <div className="space-y-3">
                {workspaces.length > 0 ? (
                  workspaces.map((ws) => {
                    const isActive = ws.id === activeWorkspaceId;
                    const fStatus = formatWorkspaceFolderStatus(ws.folder_status);
                    return (
                      <div
                        key={ws.id}
                        className={cn(
                          "rounded-2xl p-4 border space-y-3",
                          isActive
                            ? "bg-[#262624] border-emerald-500/40"
                            : "bg-[#262624]/60 border-white/[0.08]"
                        )}
                      >
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                          <div className="space-y-1 min-w-0">
                            {/* Prominent Folder Name (Section 6: Tampilkan nama folder yang dipilih sebagai informasi utama) */}
                            <div className="flex items-center gap-2 flex-wrap">
                              <FolderOpen size={17} className="text-[#D97757] shrink-0" />
                              <span className="text-[16px] font-semibold text-zinc-100">
                                {ws.name}
                              </span>
                              {isActive && <StatusBadge tone="accent" label="Ruang Kerja Aktif" />}
                              <StatusBadge
                                tone={fStatus.tone}
                                label={ws.folder_status_label || fStatus.label}
                              />
                            </div>

                            {/* Secondary Full Path with Copy Button */}
                            <div className="flex items-center gap-2 text-xs text-zinc-400">
                              <span className="font-mono truncate" title={ws.folder_path}>
                                Lokasi detail: {ws.folder_path}
                              </span>
                              <button
                                type="button"
                                onClick={() => handleCopyPath(ws.id, ws.folder_path)}
                                title="Salin lokasi lengkap folder"
                                className="inline-flex items-center gap-1 rounded-md bg-white/[0.06] hover:bg-white/[0.12] px-2 py-0.5 text-[11px] text-zinc-300 shrink-0"
                              >
                                {copiedPathId === ws.id ? (
                                  <Check size={11} className="text-emerald-400" />
                                ) : (
                                  <Copy size={11} />
                                )}
                                <span>{copiedPathId === ws.id ? "Disalin" : "Salin"}</span>
                              </button>
                            </div>
                          </div>

                          {/* Folder Actions: Buka folder, Ganti folder, Jadikan Aktif, Hapus */}
                          <div className="flex flex-wrap items-center gap-2 shrink-0">
                            <button
                              type="button"
                              onClick={() => void handleOpenFolderInOS(ws.folder_path)}
                              className="rounded-xl bg-white/[0.07] hover:bg-white/[0.13] border border-white/[0.1] px-3 py-1.5 text-xs font-medium text-zinc-100 flex items-center gap-1.5 transition-colors"
                            >
                              <ExternalLink size={12} />
                              <span>Buka folder</span>
                            </button>

                            <button
                              type="button"
                              onClick={() => void handlePickNativeFolder(ws)}
                              className="rounded-xl bg-white/[0.07] hover:bg-white/[0.13] border border-white/[0.1] px-3 py-1.5 text-xs font-medium text-zinc-100 flex items-center gap-1.5 transition-colors"
                            >
                              <FolderPlus size={12} />
                              <span>Ganti folder…</span>
                            </button>

                            {!isActive && (
                              <button
                                type="button"
                                onClick={() => setActiveWorkspace(ws.id)}
                                className="rounded-xl bg-emerald-600 hover:bg-emerald-500 px-3 py-1.5 text-xs font-semibold text-white transition-colors"
                              >
                                Gunakan Folder Ini
                              </button>
                            )}

                            {workspaces.length > 1 && (
                              <button
                                type="button"
                                onClick={() => void removeWorkspaceFolder(ws.id)}
                                title="Keluarkan folder ini dari daftar ruang kerja"
                                className="rounded-xl p-1.5 text-zinc-400 hover:text-rose-300 hover:bg-rose-500/15 transition-colors"
                              >
                                <Trash2 size={15} />
                              </button>
                            )}
                          </div>
                        </div>

                        {/* Recovery Hint if folder is inaccessible or read-only (Section 6) */}
                        {ws.recovery_hint && (
                          <div className="rounded-xl bg-amber-500/10 border border-amber-500/30 p-3 text-xs text-amber-200 flex items-center justify-between gap-3">
                            <span>
                              <strong>Langkah pemulihan:</strong> {ws.recovery_hint}
                            </span>
                            <button
                              type="button"
                              onClick={() => void handlePickNativeFolder(ws)}
                              className="rounded-lg bg-amber-500/20 hover:bg-amber-500/30 px-2.5 py-1 font-semibold text-amber-100 shrink-0"
                            >
                              Pilih Lokasi Baru
                            </button>
                          </div>
                        )}
                      </div>
                    );
                  })
                ) : (
                  <div className="rounded-2xl bg-[#262624]/60 border border-dashed border-white/[0.1] p-6 text-center space-y-3">
                    <p className="text-[14px] font-semibold text-zinc-100">
                      Belum ada folder ruang kerja yang dipilih
                    </p>
                    <p className="text-xs text-zinc-400 max-w-md mx-auto">
                      Klik tombol <strong>Pilih folder…</strong> untuk membuka file manager komputer
                      Anda dan memilih folder tempat dokumen kerja Anda disimpan.
                    </p>
                    <button
                      type="button"
                      onClick={() => void handlePickNativeFolder(null)}
                      className="inline-flex items-center gap-2 rounded-xl bg-[#D97757] hover:bg-[#c96a4b] px-4 py-2 text-xs font-semibold text-white"
                    >
                      <FolderPlus size={14} />
                      <span>Pilih folder…</span>
                    </button>
                  </div>
                )}
              </div>

              {/* Default App Storage Location & Restore Default Button (Section 6) */}
              <div className="rounded-xl bg-[#262624] border border-white/[0.07] p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-3">
                <div className="space-y-0.5">
                  <div className="text-[13.5px] font-semibold text-zinc-100">
                    Lokasi Penyimpanan Internal AKSA
                  </div>
                  <p className="text-xs text-zinc-300">
                    Folder sistem tempat AKSA menyimpan pengaturan dan memori internal:{" "}
                    <span className="font-mono text-zinc-400">
                      {rootDirInfo?.root_path || "Lokasi standar aplikasi perangkat"}
                    </span>
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => void handleResetDefaultRootDir()}
                  className="rounded-xl bg-white/[0.07] hover:bg-white/[0.13] border border-white/[0.1] px-3.5 py-2 text-xs font-medium text-zinc-200 shrink-0"
                >
                  Kembalikan ke lokasi default
                </button>
              </div>
            </div>
          </div>
        )}

        {/* =================================================================
            4. UMUM
           ================================================================= */}
        {activeCategory === "umum" && (
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
                  Pemilihan Model AI Fleksibel
                </div>
                <p className="text-xs text-zinc-300">
                  Setiap agen mendukung mode <strong>Otomatis (direkomendasikan)</strong> maupun{" "}
                  <strong>Pilih sendiri (Manual)</strong> di halaman Struktur Tim AI.
                </p>
                <StatusBadge tone="accent" label="Otomatis & Manual tersedia" />
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
        )}

        {/* =================================================================
            5. PRIVASI & DATA
           ================================================================= */}
        {activeCategory === "privasi_data" && (
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
                  onClick={() => void handleSelectPrivacyMode(opt.id)}
                  className={cn(
                    "rounded-xl p-4 border text-left space-y-2 transition-all",
                    privacyMode === opt.id
                      ? "bg-[#262624] border-[#D97757] ring-1 ring-[#D97757]/30"
                      : "bg-[#262624]/60 border-white/[0.07] hover:border-white/[0.16]"
                  )}
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
        )}

        {/* =================================================================
            6. JARINGAN
           ================================================================= */}
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
                <div className="text-[14px] font-semibold text-zinc-100">
                  Server AI Lokal (Ollama)
                </div>
                <p className="text-xs text-zinc-300">
                  Alamat lokal standar <code>127.0.0.1:11434</code> tanpa lalu lintas internet luar.
                </p>
                <StatusBadge
                  tone={engineHealth.ollama_online ? "success" : "neutral"}
                  label={engineHealth.ollama_online ? "Terhubung" : "Tidak aktif"}
                />
              </div>

              <div className="rounded-xl bg-[#262624] border border-white/[0.07] p-4 space-y-2">
                <div className="text-[14px] font-semibold text-zinc-100">Integrasi Telegram</div>
                <p className="text-xs text-zinc-300">
                  Menggunakan koneksi aman tanpa membuka port masuk pada jaringan Anda.
                </p>
                <StatusBadge
                  tone={engineHealth.telegram_connected ? "success" : "neutral"}
                  label={engineHealth.telegram_connected ? "Terhubung" : "Belum dihubungkan"}
                />
              </div>
            </div>
          </div>
        )}

        {/* =================================================================
            7. LANJUTAN
           ================================================================= */}
        {activeCategory === "lanjutan" && (
          <div className="space-y-6">
            <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 md:p-6 space-y-4">
              <SectionHeader
                icon={<Sliders size={18} className="text-sky-400" />}
                title="Daftarkan ID Model Kustom (Mode Lanjutan)"
                description="Tambahkan ID model spesifik dari penyedia AI Anda jika belum tercantum pada daftar standar."
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
                  className="rounded-xl bg-[#262624] border border-white/[0.1] px-3.5 py-2.5 text-[13px] text-zinc-100"
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
                  className="flex-1 rounded-xl bg-[#262624] border border-white/[0.1] px-3.5 py-2.5 text-[13px] text-zinc-100"
                />

                <button
                  type="submit"
                  disabled={!customModelId.trim()}
                  className="rounded-xl bg-[#D97757] hover:bg-[#c96a4b] disabled:opacity-40 text-white px-4 py-2.5 text-[13px] font-semibold flex items-center justify-center gap-1.5 shrink-0"
                >
                  <Plus size={15} />
                  <span>Daftarkan Model Kustom</span>
                </button>
              </form>
            </div>

            <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 md:p-6 space-y-4">
              <SectionHeader
                icon={<Zap size={18} className="text-amber-400" />}
                title="Statistik Efisiensi Pemakaian Kuota (Token)"
                description="Ringkasan penghematan kuota AI melalui pemisahan konteks agen pendukung."
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

        {/* =================================================================
            8. INFORMASI APLIKASI
           ================================================================= */}
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
                  <span className="text-zinc-400">Tema Aktif:</span>
                  <span className="text-zinc-200">
                    {themeMode === "system"
                      ? `Ikuti sistem (${resolvedTheme === "dark" ? "Gelap" : "Terang"})`
                      : themeMode === "light"
                      ? "Terang"
                      : "Gelap"}
                  </span>
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
                  AKSA harus sederhana di permukaan, transparan dalam meminta izin, dan tetap
                  canggih di dalam. Seluruh akses file dan aplikasi berada di bawah kendali serta
                  persetujuan Anda.
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
