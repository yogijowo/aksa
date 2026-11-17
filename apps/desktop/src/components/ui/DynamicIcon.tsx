import React from "react";
import { motion } from "framer-motion";
import {
  Cpu,
  Server,
  Sparkles,
  BrainCircuit,
  Bot,
  Cloud,
  Zap,
  Network,
  FolderOpen,
  FileSpreadsheet,
  FileText,
  Presentation,
  FileCheck2,
  BookOpenCheck,
  MonitorCog,
  Terminal,
  MousePointerClick,
  PlugZap,
  Search,
} from "lucide-react";
import type { ModelProvider } from "@/types/aksa";

export const AnimatedBrandIcon: React.FC<{ size?: number }> = ({ size = 15 }) => (
  <motion.div
    whileHover={{ scale: 1.06 }}
    whileTap={{ scale: 0.95 }}
    transition={{ type: "spring", stiffness: 400, damping: 22 }}
    className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#D97757]/15 border border-[#D97757]/30 text-[#D97757]"
  >
    <Sparkles size={size} strokeWidth={1.9} className="text-[#D97757]" />
  </motion.div>
);

export const ProviderIcon: React.FC<{
  provider: ModelProvider;
  size?: number;
  className?: string;
}> = ({ provider, size = 12, className = "" }) => {
  switch (provider) {
    case "ollama":
      return <Cpu size={size} strokeWidth={1.75} className={`text-emerald-400/90 shrink-0 ${className}`} />;
    case "lmstudio":
      return <Server size={size} strokeWidth={1.75} className={`text-emerald-400/90 shrink-0 ${className}`} />;
    case "gemini":
      return <Sparkles size={size} strokeWidth={1.75} className={`text-sky-400/90 shrink-0 ${className}`} />;
    case "anthropic":
      return <BrainCircuit size={size} strokeWidth={1.75} className={`text-[#D97757] shrink-0 ${className}`} />;
    case "deepseek":
      return <Bot size={size} strokeWidth={1.75} className={`text-indigo-400/90 shrink-0 ${className}`} />;
    case "groq":
      return <Zap size={size} strokeWidth={1.75} className={`text-amber-400/90 shrink-0 ${className}`} />;
    default:
      return <Cloud size={size} strokeWidth={1.75} className={`text-zinc-400 shrink-0 ${className}`} />;
  }
};

export const ToolCategoryIcon: React.FC<{
  category: string;
  size?: number;
  className?: string;
}> = ({ category, size = 13, className = "" }) => {
  switch (category) {
    case "delegation":
      return <Network size={size} strokeWidth={1.75} className={`text-zinc-400 shrink-0 ${className}`} />;
    case "filesystem":
      return <FolderOpen size={size} strokeWidth={1.75} className={`text-zinc-400 shrink-0 ${className}`} />;
    case "office_excel":
      return <FileSpreadsheet size={size} strokeWidth={1.75} className={`text-emerald-400/90 shrink-0 ${className}`} />;
    case "office_word":
      return <FileText size={size} strokeWidth={1.75} className={`text-sky-400/90 shrink-0 ${className}`} />;
    case "office_ppt":
      return <Presentation size={size} strokeWidth={1.75} className={`text-amber-400/90 shrink-0 ${className}`} />;
    case "pdf_tools":
      return <FileCheck2 size={size} strokeWidth={1.75} className={`text-rose-400/90 shrink-0 ${className}`} />;
    case "rag_search":
      return <BookOpenCheck size={size} strokeWidth={1.75} className={`text-[#D97757] shrink-0 ${className}`} />;
    case "os_automation":
      return <MonitorCog size={size} strokeWidth={1.75} className={`text-zinc-400 shrink-0 ${className}`} />;
    case "uv_python":
      return <Terminal size={size} strokeWidth={1.75} className={`text-zinc-400 shrink-0 ${className}`} />;
    case "computer_use":
      return <MousePointerClick size={size} strokeWidth={1.75} className={`text-zinc-400 shrink-0 ${className}`} />;
    case "mcp":
      return <PlugZap size={size} strokeWidth={1.75} className={`text-zinc-400 shrink-0 ${className}`} />;
    default:
      return <Search size={size} strokeWidth={1.75} className={`text-zinc-400 shrink-0 ${className}`} />;
  }
};
