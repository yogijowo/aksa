import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import type {
  AgentNodeConfig,
  ModelProvider,
  ProviderTokenStatus,
  WorkspaceFolderStatus,
} from "@/types/aksa";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

export function formatNumberID(value: number): string {
  return new Intl.NumberFormat("id-ID").format(value);
}

export function extractFolderDisplayName(folderPath: string, customName?: string): string {
  if (customName && customName.trim()) {
    return customName.trim();
  }
  const clean = (folderPath || "").trim().replace(/[\\/]+$/, "");
  if (!clean) return "Folder Ruang Kerja";
  const parts = clean.split(/[\\/]/).filter(Boolean);
  return parts[parts.length - 1] || clean;
}

export function getProviderBadgeStyle(provider: ModelProvider): {
  label: string;
  badgeClass: string;
  className: string;
  isLocal: boolean;
} {
  switch (provider) {
    case "ollama":
      return {
        label: "Ollama Lokal",
        badgeClass: "bg-white/[0.04] text-zinc-300 border-white/[0.08]",
        className: "bg-white/[0.04] text-zinc-300 border-white/[0.08]",
        isLocal: true,
      };
    case "lmstudio":
      return {
        label: "LM Studio Lokal",
        badgeClass: "bg-white/[0.04] text-zinc-300 border-white/[0.08]",
        className: "bg-white/[0.04] text-zinc-300 border-white/[0.08]",
        isLocal: true,
      };
    case "gemini":
      return {
        label: "Google Gemini",
        badgeClass: "bg-white/[0.04] text-zinc-300 border-white/[0.08]",
        className: "bg-white/[0.04] text-zinc-300 border-white/[0.08]",
        isLocal: false,
      };
    case "anthropic":
      return {
        label: "Anthropic Claude",
        badgeClass: "bg-white/[0.04] text-zinc-300 border-white/[0.08]",
        className: "bg-white/[0.04] text-zinc-300 border-white/[0.08]",
        isLocal: false,
      };
    case "deepseek":
      return {
        label: "DeepSeek",
        badgeClass: "bg-white/[0.04] text-zinc-300 border-white/[0.08]",
        className: "bg-white/[0.04] text-zinc-300 border-white/[0.08]",
        isLocal: false,
      };
    case "openai":
      return {
        label: "OpenAI",
        badgeClass: "bg-white/[0.04] text-zinc-300 border-white/[0.08]",
        className: "bg-white/[0.04] text-zinc-300 border-white/[0.08]",
        isLocal: false,
      };
    case "groq":
      return {
        label: "Groq Cloud",
        badgeClass: "bg-white/[0.04] text-zinc-300 border-white/[0.08]",
        className: "bg-white/[0.04] text-zinc-300 border-white/[0.08]",
        isLocal: false,
      };
    case "openrouter":
      return {
        label: "OpenRouter",
        badgeClass: "bg-white/[0.04] text-zinc-300 border-white/[0.08]",
        className: "bg-white/[0.04] text-zinc-300 border-white/[0.08]",
        isLocal: false,
      };
    default:
      return {
        label: String(provider).toUpperCase(),
        badgeClass: "bg-white/[0.04] text-zinc-300 border-white/[0.08]",
        className: "bg-white/[0.04] text-zinc-300 border-white/[0.08]",
        isLocal: false,
      };
  }
}

export interface HumanModelMetadata {
  provider: ModelProvider;
  model_id: string;
  friendlyName: string;
  capabilitiesLabel: string;
  contextWindowLabel: string;
  costTierLabel: string;
  supportsToolCalling: boolean;
}

export const MODEL_METADATA_LIST: HumanModelMetadata[] = [
  // Gemini
  {
    provider: "gemini",
    model_id: "gemini-4-carbon",
    friendlyName: "Gemini 4 Carbon",
    capabilitiesLabel: "Koordinasi tim, strategi & penalaran mendalam",
    contextWindowLabel: "Konteks 2M token",
    costTierLabel: "Model Unggulan",
    supportsToolCalling: true,
  },
  {
    provider: "gemini",
    model_id: "gemini-4-argon",
    friendlyName: "Gemini 4 Argon",
    capabilitiesLabel: "Multimodal, analisis dokumen panjang & agen",
    contextWindowLabel: "Konteks 1M token",
    costTierLabel: "Seimbang",
    supportsToolCalling: true,
  },
  {
    provider: "gemini",
    model_id: "gemini-4-hydrogen",
    friendlyName: "Gemini 4 Hydrogen",
    capabilitiesLabel: "Pemrosesan cepat & efisiensi kuota harian",
    contextWindowLabel: "Konteks 1M token",
    costTierLabel: "Hemat Kuota",
    supportsToolCalling: true,
  },
  {
    provider: "gemini",
    model_id: "gemini-3.8-flash",
    friendlyName: "Gemini 3.8 Flash",
    capabilitiesLabel: "Respons cepat untuk administrasi & ringkasan",
    contextWindowLabel: "Konteks 1M token",
    costTierLabel: "Hemat Kuota",
    supportsToolCalling: true,
  },
  {
    provider: "gemini",
    model_id: "gemini-3.5-flash-lite",
    friendlyName: "Gemini 3.5 Flash-Lite",
    capabilitiesLabel: "Tugas ringan berkecepatan tinggi",
    contextWindowLabel: "Konteks 512K token",
    costTierLabel: "Sangat Hemat Kuota",
    supportsToolCalling: true,
  },
  // Anthropic
  {
    provider: "anthropic",
    model_id: "claude-fable-5-2",
    friendlyName: "Claude Fable 5.2",
    capabilitiesLabel: "Penalaran mendalam & sintesis dokumen kompleks",
    contextWindowLabel: "Konteks 500K token",
    costTierLabel: "Model Unggulan",
    supportsToolCalling: true,
  },
  {
    provider: "anthropic",
    model_id: "claude-opus-5-5",
    friendlyName: "Claude Opus 5.5",
    capabilitiesLabel: "Telaah dokumen panjang & penulisan laporan",
    contextWindowLabel: "Konteks 400K token",
    costTierLabel: "Model Unggulan",
    supportsToolCalling: true,
  },
  {
    provider: "anthropic",
    model_id: "claude-sonnet-5-5",
    friendlyName: "Claude Sonnet 5.5",
    capabilitiesLabel: "Pemrograman, kontrol aplikasi & automasi kerja",
    contextWindowLabel: "Konteks 200K token",
    costTierLabel: "Seimbang",
    supportsToolCalling: true,
  },
  {
    provider: "anthropic",
    model_id: "claude-haiku-5-5",
    friendlyName: "Claude Haiku 5.5",
    capabilitiesLabel: "Tanya jawab ringkas & klasifikasi dokumen",
    contextWindowLabel: "Konteks 200K token",
    costTierLabel: "Hemat Kuota",
    supportsToolCalling: true,
  },
  // OpenAI
  {
    provider: "openai",
    model_id: "gpt-6.2-astra",
    friendlyName: "GPT-6.2 Astra",
    capabilitiesLabel: "Penalaran tingkat lanjut & koordinasi agen",
    contextWindowLabel: "Konteks 256K token",
    costTierLabel: "Model Unggulan",
    supportsToolCalling: true,
  },
  {
    provider: "openai",
    model_id: "gpt-6.2-sol",
    friendlyName: "GPT-6.2 Sol",
    capabilitiesLabel: "Seimbang untuk dokumen, data & instruksi harian",
    contextWindowLabel: "Konteks 256K token",
    costTierLabel: "Seimbang",
    supportsToolCalling: true,
  },
  {
    provider: "openai",
    model_id: "gpt-6.1-sol",
    friendlyName: "GPT-6.1 Sol",
    capabilitiesLabel: "Produktivitas kantor & penyusunan laporan",
    contextWindowLabel: "Konteks 128K token",
    costTierLabel: "Seimbang",
    supportsToolCalling: true,
  },
  {
    provider: "openai",
    model_id: "gpt-6-luna",
    friendlyName: "GPT-6 Luna",
    capabilitiesLabel: "Cepat & hemat biaya untuk tugas rutin",
    contextWindowLabel: "Konteks 128K token",
    costTierLabel: "Hemat Kuota",
    supportsToolCalling: true,
  },
  // DeepSeek
  {
    provider: "deepseek",
    model_id: "deepseek-v4-pro",
    friendlyName: "DeepSeek V4 Pro",
    capabilitiesLabel: "Analisis angka, rumus Excel & pemrograman",
    contextWindowLabel: "Konteks 128K token",
    costTierLabel: "Hemat Kuota",
    supportsToolCalling: true,
  },
  {
    provider: "deepseek",
    model_id: "deepseek-flash",
    friendlyName: "DeepSeek V4.1 Flash",
    capabilitiesLabel: "Olah tabel Excel & dokumen cepat",
    contextWindowLabel: "Konteks 128K token",
    costTierLabel: "Sangat Hemat Kuota",
    supportsToolCalling: true,
  },
  {
    provider: "deepseek",
    model_id: "deepseek-chat",
    friendlyName: "DeepSeek Chat",
    capabilitiesLabel: "Pembuatan dokumen Word, Excel, PPT & PDF",
    contextWindowLabel: "Konteks 128K token",
    costTierLabel: "Hemat Kuota",
    supportsToolCalling: true,
  },
  {
    provider: "deepseek",
    model_id: "deepseek-reasoner",
    friendlyName: "DeepSeek R1 Reasoner",
    capabilitiesLabel: "Logika mendalam & verifikasi perhitungan",
    contextWindowLabel: "Konteks 128K token",
    costTierLabel: "Seimbang",
    supportsToolCalling: false,
  },
  // Groq
  {
    provider: "groq",
    model_id: "meta-llama/llama-4-maverick-17b-128e-instruct",
    friendlyName: "Llama 4 Maverick 17B",
    capabilitiesLabel: "Inferensi sangat cepat & instruksi kerja",
    contextWindowLabel: "Konteks 128K token",
    costTierLabel: "Hemat Kuota",
    supportsToolCalling: true,
  },
  {
    provider: "groq",
    model_id: "meta-llama/llama-4-scout-17b-16e-instruct",
    friendlyName: "Llama 4 Scout 17B",
    capabilitiesLabel: "Pencarian cepat & ringkasan dokumen",
    contextWindowLabel: "Konteks 128K token",
    costTierLabel: "Sangat Hemat Kuota",
    supportsToolCalling: true,
  },
  {
    provider: "groq",
    model_id: "qwen/qwen3-32b",
    friendlyName: "Qwen 3 32B (Groq)",
    capabilitiesLabel: "Bahasa Indonesia natural & analisis dokumen",
    contextWindowLabel: "Konteks 128K token",
    costTierLabel: "Hemat Kuota",
    supportsToolCalling: true,
  },
  {
    provider: "groq",
    model_id: "deepseek-r1-distill-llama-70b",
    friendlyName: "DeepSeek R1 Distill 70B",
    capabilitiesLabel: "Penalaran cepat berbasis Llama 70B",
    contextWindowLabel: "Konteks 128K token",
    costTierLabel: "Seimbang",
    supportsToolCalling: false,
  },
  // OpenRouter
  {
    provider: "openrouter",
    model_id: "openrouter/auto",
    friendlyName: "OpenRouter Otomatis",
    capabilitiesLabel: "Pemilihan rute model terbaik secara otomatis",
    contextWindowLabel: "Konteks hingga 200K token",
    costTierLabel: "Seimbang",
    supportsToolCalling: true,
  },
  {
    provider: "openrouter",
    model_id: "anthropic/claude-sonnet-5-5",
    friendlyName: "Claude Sonnet 5.5 (OpenRouter)",
    capabilitiesLabel: "Agen, dokumen & pemrograman via OpenRouter",
    contextWindowLabel: "Konteks 200K token",
    costTierLabel: "Seimbang",
    supportsToolCalling: true,
  },
  {
    provider: "openrouter",
    model_id: "google/gemini-4-carbon",
    friendlyName: "Gemini 4 Carbon (OpenRouter)",
    capabilitiesLabel: "Koordinasi & analisis mendalam via OpenRouter",
    contextWindowLabel: "Konteks 1M token",
    costTierLabel: "Model Unggulan",
    supportsToolCalling: true,
  },
  {
    provider: "openrouter",
    model_id: "deepseek/deepseek-v4-pro",
    friendlyName: "DeepSeek V4 Pro (OpenRouter)",
    capabilitiesLabel: "Analisis tabel & kode via OpenRouter",
    contextWindowLabel: "Konteks 128K token",
    costTierLabel: "Hemat Kuota",
    supportsToolCalling: true,
  },
  // Ollama Local
  {
    provider: "ollama",
    model_id: "qwen3.8:8b",
    friendlyName: "Qwen 3.8 8B (Lokal)",
    capabilitiesLabel: "Pencarian dokumen & tugas harian 100% di perangkat Anda",
    contextWindowLabel: "Konteks 32K token",
    costTierLabel: "Gratis (AI Lokal)",
    supportsToolCalling: true,
  },
  {
    provider: "ollama",
    model_id: "qwen3.8:14b",
    friendlyName: "Qwen 3.8 14B (Lokal)",
    capabilitiesLabel: "Akurasi tinggi untuk ringkasan & dokumen lokal",
    contextWindowLabel: "Konteks 32K token",
    costTierLabel: "Gratis (AI Lokal)",
    supportsToolCalling: true,
  },
  {
    provider: "ollama",
    model_id: "qwen3-coder:30b",
    friendlyName: "Qwen 3 Coder 30B (Lokal)",
    capabilitiesLabel: "Pemrograman & skrip data lokal tanpa internet",
    contextWindowLabel: "Konteks 32K token",
    costTierLabel: "Gratis (AI Lokal)",
    supportsToolCalling: true,
  },
  {
    provider: "ollama",
    model_id: "gemma4:12b",
    friendlyName: "Google Gemma 4 12B (Lokal)",
    capabilitiesLabel: "Penulisan & analisis dokumen lokal",
    contextWindowLabel: "Konteks 32K token",
    costTierLabel: "Gratis (AI Lokal)",
    supportsToolCalling: true,
  },
  {
    provider: "ollama",
    model_id: "deepseek-r1:8b",
    friendlyName: "DeepSeek R1 8B (Lokal)",
    capabilitiesLabel: "Penalaran logika lokal tanpa kuota cloud",
    contextWindowLabel: "Konteks 32K token",
    costTierLabel: "Gratis (AI Lokal)",
    supportsToolCalling: false,
  },
  {
    provider: "ollama",
    model_id: "llama4:scout",
    friendlyName: "Llama 4 Scout (Lokal)",
    capabilitiesLabel: "Asisten umum lokal di komputer Anda",
    contextWindowLabel: "Konteks 32K token",
    costTierLabel: "Gratis (AI Lokal)",
    supportsToolCalling: true,
  },
  // LM Studio Local
  {
    provider: "lmstudio",
    model_id: "qwen3.8-8b-instruct",
    friendlyName: "Qwen 3.8 8B Instruct (LM Studio)",
    capabilitiesLabel: "Pemrosesan dokumen lokal melalui LM Studio",
    contextWindowLabel: "Konteks 32K token",
    costTierLabel: "Gratis (AI Lokal)",
    supportsToolCalling: true,
  },
  {
    provider: "lmstudio",
    model_id: "gemma-4-12b-it",
    friendlyName: "Gemma 4 12B Instruct (LM Studio)",
    capabilitiesLabel: "Penulisan & tanya jawab lokal via LM Studio",
    contextWindowLabel: "Konteks 32K token",
    costTierLabel: "Gratis (AI Lokal)",
    supportsToolCalling: true,
  },
  {
    provider: "lmstudio",
    model_id: "deepseek-r1-distill-qwen-14b",
    friendlyName: "DeepSeek R1 Distill 14B (LM Studio)",
    capabilitiesLabel: "Analisis logika lokal via LM Studio",
    contextWindowLabel: "Konteks 32K token",
    costTierLabel: "Gratis (AI Lokal)",
    supportsToolCalling: false,
  },
];

export function getHumanModelInfo(
  provider: ModelProvider,
  modelId: string
): HumanModelMetadata {
  const found = MODEL_METADATA_LIST.find(
    (m) => m.provider === provider && m.model_id === modelId
  );
  if (found) return found;

  const isLocal = provider === "ollama" || provider === "lmstudio";
  const friendly = modelId
    .replace(/^(models\/|anthropic\/|google\/|openai\/|deepseek\/|meta-llama\/|qwen\/)/, "")
    .replace(/[-_:]/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());

  return {
    provider,
    model_id: modelId,
    friendlyName: friendly || modelId,
    capabilitiesLabel: isLocal
      ? "Model AI lokal berjalan langsung di perangkat Anda"
      : "Model AI kustom sesuai konfigurasi penyedia",
    contextWindowLabel: isLocal ? "Konteks lokal" : "Konteks standar penyedia",
    costTierLabel: isLocal ? "Gratis (AI Lokal)" : "Sesuai tarif penyedia",
    supportsToolCalling: !modelId.toLowerCase().includes("reasoner") && !modelId.toLowerCase().includes("r1"),
  };
}

export function wouldCreateAgentCycle(
  agents: Pick<AgentNodeConfig, "id" | "parent_id">[],
  agentId: string,
  candidateParentId: string | null
): boolean {
  if (!candidateParentId) return false;
  if (candidateParentId === agentId) return true;

  const byId = new Map(agents.map((a) => [a.id, a]));
  const visited = new Set<string>();
  let curr: string | null = candidateParentId;
  let depth = 0;

  while (curr !== null && depth <= agents.length + 2) {
    if (curr === agentId) return true;
    if (visited.has(curr)) return true;
    visited.add(curr);
    const node = byId.get(curr);
    curr = node ? node.parent_id : null;
    depth += 1;
  }
  return false;
}

export function computeAutoHierarchyLayout(
  agents: Pick<AgentNodeConfig, "id" | "parent_id">[]
): Record<string, { position_x: number; position_y: number; tier_level: number }> {
  const result: Record<string, { position_x: number; position_y: number; tier_level: number }> = {};
  if (agents.length === 0) return result;

  const byId = new Map(agents.map((a) => [a.id, a]));
  const childrenMap = new Map<string | null, string[]>();

  for (const agt of agents) {
    const pid = agt.parent_id && byId.has(agt.parent_id) ? agt.parent_id : null;
    const list = childrenMap.get(pid) ?? [];
    list.push(agt.id);
    childrenMap.set(pid, list);
  }

  const levels = new Map<number, string[]>();
  const visited = new Set<string>();

  const traverse = (id: string, tier: number) => {
    if (visited.has(id)) return;
    visited.add(id);
    const tierList = levels.get(tier) ?? [];
    tierList.push(id);
    levels.set(tier, tierList);

    const kids = childrenMap.get(id) ?? [];
    for (const kidId of kids) {
      traverse(kidId, tier + 1);
    }
  };

  const roots = childrenMap.get(null) ?? [agents[0].id];
  for (const rId of roots) {
    traverse(rId, 0);
  }
  for (const agt of agents) {
    if (!visited.has(agt.id)) {
      traverse(agt.id, 1);
    }
  }

  const NODE_WIDTH = 300;
  const H_GAP = 120;
  const V_GAP = 330;
  const CENTER_X = 610;

  for (const [tier, ids] of levels.entries()) {
    const totalWidth = ids.length * NODE_WIDTH + Math.max(0, ids.length - 1) * H_GAP;
    const startX = Math.max(40, Math.round(CENTER_X - totalWidth / 2));
    ids.forEach((id, idx) => {
      result[id] = {
        position_x: startX + idx * (NODE_WIDTH + H_GAP),
        position_y: 30 + tier * V_GAP,
        tier_level: tier,
      };
    });
  }

  return result;
}

export function formatProviderTokenStatus(
  status?: ProviderTokenStatus,
  isLocal: boolean = false
): {
  label: string;
  tone: "success" | "danger" | "warning" | "neutral" | "accent";
  description: string;
} {
  if (isLocal) {
    if (status === "connected") {
      return {
        label: "Terhubung (Lokal Aktif)",
        tone: "success",
        description: "Server AI lokal berjalan di komputer Anda dan siap digunakan.",
      };
    }
    return {
      label: "Belum aktif (Lokal)",
      tone: "neutral",
      description: "Server AI lokal belum terdeteksi berjalan di perangkat ini.",
    };
  }

  switch (status) {
    case "connected":
      return {
        label: "Terhubung",
        tone: "success",
        description: "Token tersimpan dan tes koneksi terakhir berhasil diverifikasi.",
      };
    case "token_saved":
      return {
        label: "Token tersimpan",
        tone: "accent",
        description: "Token sudah tersimpan aman di perangkat. Klik Uji koneksi untuk memastikan layanan siap.",
      };
    case "needs_check":
      return {
        label: "Perlu diperiksa",
        tone: "warning",
        description: "Token tersimpan, namun belum diuji pada sesi ini.",
      };
    case "connection_failed":
      return {
        label: "Koneksi gagal",
        tone: "danger",
        description: "Pemeriksaan koneksi terakhir gagal. Periksa kembali token API atau jaringan Anda.",
      };
    case "not_connected":
    default:
      return {
        label: "Belum dihubungkan",
        tone: "neutral",
        description: "Belum ada token API yang disimpan untuk penyedia ini.",
      };
  }
}

export function formatWorkspaceFolderStatus(status?: WorkspaceFolderStatus): {
  label: string;
  tone: "success" | "danger" | "warning" | "neutral" | "accent";
} {
  switch (status) {
    case "accessible":
      return { label: "Dapat diakses", tone: "success" };
    case "read_only":
      return { label: "Hanya baca (Read-only)", tone: "warning" };
    case "not_found":
      return { label: "Tidak ditemukan", tone: "danger" };
    case "permission_denied":
      return { label: "Izin ditolak", tone: "danger" };
    case "unavailable":
      return { label: "Tidak tersedia", tone: "neutral" };
    default:
      return { label: "Dapat diakses", tone: "success" };
  }
}

export const TOOL_CATEGORY_LABELS: Record<string, string> = {
  delegation: "Koordinasi Agen Pendukung",
  filesystem: "Kelola Folder & File",
  office_excel: "Olahan Tabel Excel (.xlsx)",
  office_word: "Dokumen Word (.docx)",
  office_ppt: "Presentasi PowerPoint (.pptx)",
  pdf_tools: "Baca & Buat PDF",
  rag_search: "Pencarian dalam Dokumen",
  os_automation: "Kendali Aplikasi Komputer",
  uv_python: "Pemrosesan Data & Skrip",
  computer_use: "Kontrol Layar & Keyboard",
  mcp: "Koneksi Layanan Eksternal",
};

export const TOOL_CATEGORY_DESCRIPTIONS: Record<string, string> = {
  delegation: "Membagi pekerjaan ke agen pendukung yang sesuai.",
  filesystem: "Membaca dan menyimpan file di dalam ruang kerja yang diizinkan.",
  office_excel: "Membuat tabel, laporan angka, dan rumus otomatis di Excel.",
  office_word: "Menyusun surat, laporan, dan dokumen rapi di Word.",
  office_ppt: "Membuat salindia presentasi di PowerPoint.",
  pdf_tools: "Membaca isi dokumen PDF atau menyimpan laporan menjadi PDF.",
  rag_search: "Mencari informasi dan kutipan penting dari koleksi dokumen Anda.",
  os_automation: "Membantu mengoperasikan aplikasi yang sudah Anda izinkan.",
  uv_python: "Menjalankan pengolahan data otomatis di area kerja terlindungi.",
  computer_use: "Membantu klik dan ketik di layar dengan persetujuan Anda.",
  mcp: "Menghubungkan AKSA dengan layanan tambahan yang Anda aktifkan.",
};

export function formatPermissionStatusLabel(status: string): {
  label: string;
  tone: "success" | "danger" | "warning" | "neutral" | "accent";
} {
  switch (status) {
    case "GRANTED":
    case "granted":
      return { label: "Izin diberikan", tone: "success" };
    case "DENIED":
    case "REVOKED":
    case "denied":
      return { label: "Akses ditolak", tone: "danger" };
    case "NEEDS_USER_ACTION":
    case "NOT_REQUESTED":
    case "PENDING":
    case "not_granted":
      return { label: "Memerlukan tindakan Anda", tone: "warning" };
    case "automatic_sandbox":
      return { label: "Dilindungi otomatis", tone: "accent" };
    case "UNSUPPORTED":
    case "ERROR":
    default:
      return { label: "Tidak tersedia pada perangkat ini", tone: "neutral" };
  }
}
