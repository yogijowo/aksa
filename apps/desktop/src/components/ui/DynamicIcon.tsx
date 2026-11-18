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

export const AnimatedBrandIcon: React.FC<{ size?: number }> = ({ size = 18 }) => (
  <motion.div
    whileHover={{ scale: 1.06 }}
    whileTap={{ scale: 0.95 }}
    transition={{ type: "spring", stiffness: 400, damping: 22 }}
    className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#D97757]/12 border border-[#D97757]/35 text-[#D97757]"
  >
    <svg
      width={size}
      height={size}
      viewBox="0 0 256 256"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <polygon points="94,164 128,138 128,164 86,194" fill="#FFD0BF" />
      <polygon points="128,138 162,164 170,194 128,164" fill="#F09373" />
      <path
        d="M 128 36 C 135 36 141 40 144 47 L 208 191 C 211 198 206 205 198 205 L 179 205 C 173 205 168 201 166 195 L 128 80 Z"
        fill="#C65D3D"
      />
      <path
        d="M 128 36 L 128 80 L 90 195 C 88 201 83 205 77 205 L 58 205 C 50 205 45 198 48 191 L 112 47 C 115 40 121 36 128 36 Z"
        fill="#E88464"
      />
      <path
        d="M 128 103 C 129.3 111 131.8 113.5 140 115 C 131.8 116.5 129.3 119 128 127 C 126.7 119 124.2 116.5 116 115 C 124.2 113.5 126.7 111 128 103 Z"
        fill="#FFF5F0"
      />
    </svg>
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
