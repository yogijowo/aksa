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
  delegation: "Delegasi Sub-Agen",
  filesystem: "File & Folder Kerja",
  office_excel: "Microsoft Excel (.xlsx)",
  office_word: "Microsoft Word (.docx)",
  office_ppt: "PowerPoint (.pptx)",
  pdf_tools: "Dokumen PDF",
  rag_search: "Pencarian RAG",
  os_automation: "Jembatan OS / Office",
  uv_python: "Skrip Python (uv)",
  computer_use: "Kontrol Layar GUI",
  mcp: "Protokol MCP",
};
