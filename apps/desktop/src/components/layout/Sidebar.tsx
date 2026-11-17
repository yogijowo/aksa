import React from "react";
import {
  MessageSquareText,
  Network,
  LayoutGrid,
  Sparkles,
  BookOpenCheck,
  Send,
  ShieldCheck,
  Settings,
  PanelLeftClose,
  PanelLeftOpen,
  Cpu,
} from "lucide-react";
import { useAksaStore } from "@/stores/useAksaStore";
import { cn } from "@/lib/utils";
import { AnimatedBrandIcon } from "@/components/ui/DynamicIcon";
import type { NavSection } from "@/types/aksa";

const NAV_ITEMS: { id: NavSection; label: string; icon: React.ElementType }[] = [
  {
    id: "ruang_kerja",
    label: "Ruang Kerja",
    icon: MessageSquareText,
  },
  {
    id: "tim_agen",
    label: "Tim Agen",
    icon: Network,
  },
  {
    id: "aplikasi",
    label: "Aplikasi PC",
    icon: LayoutGrid,
  },
  {
    id: "keahlian",
    label: "Keahlian (Skills)",
    icon: Sparkles,
  },
  {
    id: "pengetahuan_rag",
    label: "Basis Pengetahuan",
    icon: BookOpenCheck,
  },
  {
    id: "telegram",
    label: "Koneksi Telegram",
    icon: Send,
  },
  {
    id: "izin_pc",
    label: "Izin & Akses PC",
    icon: ShieldCheck,
  },
  {
    id: "pengaturan",
    label: "Pengaturan",
    icon: Settings,
  },
];

export const Sidebar: React.FC = () => {
  const {
    activeNav,
    setActiveNav,
    isSidebarCollapsed,
    toggleSidebar,
    engineHealth,
    totalTokensUsed,
    totalTokensSaved,
  } = useAksaStore();

  const hasTokenActivity = totalTokensUsed + totalTokensSaved > 0;
  const savingsRatio = hasTokenActivity
    ? Math.round((totalTokensSaved / (totalTokensUsed + totalTokensSaved)) * 100)
    : 0;

  return (
    <aside
      className={cn(
        "flex flex-col justify-between border-r border-white/[0.06] bg-[#141413] transition-all duration-200 select-none shrink-0",
        isSidebarCollapsed ? "w-[60px]" : "w-[228px]"
      )}
    >
      {/* Top Brand Header */}
      <div>
        <div className="flex items-center justify-between h-12 px-3 border-b border-white/[0.05]">
          {!isSidebarCollapsed && (
            <div className="flex items-center gap-2.5 pl-0.5">
              <AnimatedBrandIcon size={14} />
              <div className="flex items-baseline gap-1.5">
                <span className="font-semibold tracking-tight text-[13.5px] text-zinc-100">
                  AKSA
                </span>
                <span className="text-[10px] font-medium text-zinc-500">Desktop</span>
              </div>
            </div>
          )}

          <button
            onClick={toggleSidebar}
            title={isSidebarCollapsed ? "Perluas Navigasi" : "Ciutkan Navigasi"}
            className="flex h-7 w-7 items-center justify-center rounded-lg text-zinc-500 hover:bg-white/[0.05] hover:text-zinc-200 transition-colors mx-auto"
          >
            {isSidebarCollapsed ? <PanelLeftOpen size={15} /> : <PanelLeftClose size={15} />}
          </button>
        </div>

        {/* Navigation Links (Claude Desktop Clean Single-Line Style) */}
        <nav className="p-2 space-y-0.5">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive = activeNav === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveNav(item.id)}
                title={isSidebarCollapsed ? item.label : undefined}
                className={cn(
                  "group w-full flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-left transition-all duration-150",
                  isActive
                    ? "bg-white/[0.08] text-zinc-100 font-medium"
                    : "text-zinc-400 hover:bg-white/[0.04] hover:text-zinc-200"
                )}
              >
                <Icon
                  size={16}
                  strokeWidth={1.75}
                  className={cn(
                    "shrink-0 transition-transform duration-150 group-hover:scale-105",
                    isActive ? "text-[#D97757]" : "text-zinc-500 group-hover:text-zinc-300"
                  )}
                />
                {!isSidebarCollapsed && (
                  <span className="text-[13px] truncate leading-none">{item.label}</span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Quiet Minimal Status Footer */}
      <div className="p-2.5 border-t border-white/[0.05]">
        {!isSidebarCollapsed ? (
          <div className="rounded-lg bg-white/[0.02] border border-white/[0.05] px-3 py-2.5 space-y-2">
            <div className="flex items-center justify-between text-[11px]">
              <div className="flex items-center gap-1.5 text-zinc-400">
                <Cpu size={13} className="text-zinc-500" />
                <span>Ollama Lokal</span>
              </div>
              <span className="flex items-center gap-1.5 text-[11px] text-zinc-300">
                <span
                  className={cn(
                    "h-1.5 w-1.5 rounded-full",
                    engineHealth.ollama_online ? "bg-emerald-400" : "bg-zinc-600"
                  )}
                />
                {engineHealth.ollama_online ? "Aktif" : "Nonaktif"}
              </span>
            </div>

            <div className="flex items-center justify-between text-[11px] pt-1.5 border-t border-white/[0.04]">
              <span className="text-zinc-500">Efisiensi Token</span>
              <span className="font-mono text-[11px] text-zinc-300">
                {hasTokenActivity ? `Hemat ${savingsRatio}%` : "0 Token"}
              </span>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center py-1">
            <span
              title={`Ollama Lokal: ${engineHealth.ollama_online ? "Aktif" : "Nonaktif"} • ${
                hasTokenActivity ? `Hemat ${savingsRatio}% Token` : "Belum ada token"
              }`}
              className={cn(
                "h-2 w-2 rounded-full",
                engineHealth.ollama_online ? "bg-emerald-400" : "bg-zinc-600"
              )}
            />
          </div>
        )}
      </div>
    </aside>
  );
};
