import React, { useEffect, useState } from "react";
import {
  LayoutGrid,
  RefreshCw,
  Search,
  ExternalLink,
  Activity,
  Layers,
  Sparkles,
} from "lucide-react";
import { toast } from "sonner";
import { fetchDesktopAppsRemote, refreshDesktopAppsRemote, launchDesktopAppRemote } from "@/services/engineClient";
import type { DesktopApp } from "@/types/aksa";

export const ApplicationsView: React.FC = () => {
  const [apps, setApps] = useState<DesktopApp[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [launchingId, setLaunchingId] = useState<string | null>(null);

  const loadApps = async () => {
    setLoading(true);
    try {
      const data = await fetchDesktopAppsRemote();
      if (data) setApps(data);
    } catch {
      toast.error("Gagal memuat daftar aplikasi dari sistem.");
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async () => {
    setLoading(true);
    try {
      const data = await refreshDesktopAppsRemote();
      if (data) {
        setApps(data);
        toast.success(`Berhasil memperbarui ${data.length} aplikasi terpasang di komputer.`);
      }
    } catch {
      toast.error("Gagal memindai ulang aplikasi di sistem.");
    } finally {
      setLoading(false);
    }
  };

  const handleLaunch = async (app: DesktopApp) => {
    setLaunchingId(app.id);
    try {
      const res = await launchDesktopAppRemote(app.id);
      if (res.success) {
        toast.success(res.message);
      } else {
        toast.error(res.message);
      }
    } catch (err: any) {
      toast.error(`Gagal meluncurkan aplikasi: ${err?.message || err}`);
    } finally {
      setLaunchingId(null);
    }
  };

  useEffect(() => {
    loadApps();
  }, []);

  const filteredApps = apps.filter((a) => {
    const q = search.toLowerCase();
    return (
      a.display_name.toLowerCase().includes(q) ||
      (a.publisher && a.publisher.toLowerCase().includes(q)) ||
      a.available_adapters.some((ad) => ad.toLowerCase().includes(q))
    );
  });

  return (
    <div className="flex-1 overflow-y-auto px-8 py-8 bg-[#191918] text-[#ECECEB]">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[#D97757]">
              <LayoutGrid className="w-4 h-4" />
              <span>Intelijensi Desktop &amp; Aplikasi PC</span>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-white">Aplikasi Terpasang</h1>
            <p className="text-sm text-[#9C9A92]">
              Daftar perangkat lunak yang terdeteksi di komputer Anda secara lokal tanpa membaca data pribadi.
            </p>
          </div>

          <button
            onClick={handleRefresh}
            disabled={loading}
            className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-[#242422] hover:bg-[#242428] border border-[#FFFFFF]/10 text-xs font-medium transition-all text-[#ECECEB] disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            <span>Pindai Ulang Perangkat</span>
          </button>
        </div>

        {/* Search Bar */}
        <div className="relative">
          <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-[#71716E]" />
          <input
            type="text"
            placeholder="Cari nama aplikasi, penerbit, atau adapter (misal: Excel, Chrome, Office)..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-[#21211F] border border-[#FFFFFF]/10 rounded-lg pl-10 pr-4 py-2.5 text-xs text-[#ECECEB] placeholder-[#71716E] focus:outline-none focus:border-[#D97757]/60"
          />
        </div>

        {/* Stats Row */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="p-4 rounded-xl bg-[#21211F] border border-[#FFFFFF]/10 flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-[#D97757]/15 flex items-center justify-center text-[#D97757]">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <div className="text-xl font-bold text-white">{apps.length}</div>
              <div className="text-[11px] text-[#9C9A92]">Total Aplikasi Terdeteksi</div>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-[#21211F] border border-[#FFFFFF]/10 flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-[#10B981]/15 flex items-center justify-center text-[#10B981]">
              <Activity className="w-5 h-5" />
            </div>
            <div>
              <div className="text-xl font-bold text-white">
                {apps.filter((a) => a.is_running).length}
              </div>
              <div className="text-[11px] text-[#9C9A92]">Sedang Berjalan di PC</div>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-[#21211F] border border-[#FFFFFF]/10 flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-[#8B5CF6]/15 flex items-center justify-center text-[#8B5CF6]">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <div className="text-xl font-bold text-white">
                {apps.filter((a) => a.available_adapters.some((x) => x !== "launcher")).length}
              </div>
              <div className="text-[11px] text-[#9C9A92]">Mendukung Automasi Lanjutan</div>
            </div>
          </div>
        </div>

        {/* Application Cards List */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
          {filteredApps.map((app) => (
            <div
              key={app.id}
              className="p-4 rounded-xl bg-[#21211F] border border-[#FFFFFF]/10 hover:border-[#FFFFFF]/20 transition-all flex flex-col justify-between space-y-3"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-sm text-white">{app.display_name}</span>
                    {app.is_running && (
                      <span className="flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-[#10B981]/15 text-[#10B981] border border-[#10B981]/30">
                        <span className="w-1.5 h-1.5 rounded-full bg-[#10B981] animate-pulse" />
                        Aktif
                      </span>
                    )}
                  </div>

                  <div className="text-xs text-[#9C9A92]">
                    {app.publisher || "Penerbit Terverifikasi Sistem"}
                    {app.version && <span className="ml-1.5 text-[#71716E]">v{app.version}</span>}
                  </div>
                </div>

                <button
                  onClick={() => handleLaunch(app)}
                  disabled={launchingId === app.id}
                  className="px-2.5 py-1.5 rounded-md bg-[#242428] hover:bg-[#343431] border border-[#FFFFFF]/10 text-[11px] font-medium text-[#ECECEB] flex items-center gap-1 transition-all disabled:opacity-50"
                  title="Buka aplikasi di PC"
                >
                  <ExternalLink className="w-3 h-3" />
                  <span>{launchingId === app.id ? "Membuka..." : "Buka"}</span>
                </button>
              </div>

              {/* Adapter Badges */}
              <div className="flex flex-wrap items-center gap-1.5 pt-2 border-t border-[#FFFFFF]/05">
                <span className="text-[10px] text-[#71716E]">Integrasi:</span>
                {app.available_adapters.map((ad) => (
                  <span
                    key={ad}
                    className={`px-2 py-0.5 rounded text-[10px] font-medium ${
                      ad === "office"
                        ? "bg-[#D97757]/15 text-[#D97757] border border-[#D97757]/30"
                        : ad === "browser"
                        ? "bg-[#38BDF8]/15 text-[#38BDF8] border border-[#38BDF8]/30"
                        : ad === "uia"
                        ? "bg-[#8B5CF6]/15 text-[#8B5CF6] border border-[#8B5CF6]/30"
                        : "bg-[#242428] text-[#9C9A92]"
                    }`}
                  >
                    {ad === "office"
                      ? "Office Adapter"
                      : ad === "browser"
                      ? "Browser Adapter"
                      : ad === "uia"
                      ? "UI Automation"
                      : ad === "editor"
                      ? "Code / Text"
                      : "App Launcher"}
                  </span>
                ))}
              </div>
            </div>
          ))}

          {filteredApps.length === 0 && (
            <div className="col-span-full py-12 text-center text-[#71716E] text-xs">
              Tidak ada aplikasi yang cocok dengan kata kunci "{search}".
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
