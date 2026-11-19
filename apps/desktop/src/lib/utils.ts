import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import type { ModelProvider } from "@/types/aksa";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

export function formatNumberID(value: number): string {
  return new Intl.NumberFormat("id-ID").format(value);
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
        label: "LM Studio",
        badgeClass: "bg-white/[0.04] text-zinc-300 border-white/[0.08]",
        className: "bg-white/[0.04] text-zinc-300 border-white/[0.08]",
        isLocal: true,
      };
    case "gemini":
      return {
        label: "Gemini",
        badgeClass: "bg-white/[0.04] text-zinc-300 border-white/[0.08]",
        className: "bg-white/[0.04] text-zinc-300 border-white/[0.08]",
        isLocal: false,
      };
    case "anthropic":
      return {
        label: "Claude",
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
    default:
      return {
        label: provider.toUpperCase(),
        badgeClass: "bg-white/[0.04] text-zinc-300 border-white/[0.08]",
        className: "bg-white/[0.04] text-zinc-300 border-white/[0.08]",
        isLocal: false,
      };
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
