import React, { useEffect, Suspense } from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopHeader } from "@/components/layout/TopHeader";
import { ArtifactDrawer } from "@/components/layout/ArtifactDrawer";
import { WorkspaceChatView } from "@/components/workspace/WorkspaceChatView";
import { HITLApprovalModal } from "@/components/workspace/HITLApprovalModal";
import { useAksaStore } from "@/stores/useAksaStore";

// Code splitting (P3-2): lazy load large modules (React Flow canvas & Feature panels)
const AgentHierarchyView = React.lazy(() =>
  import("@/components/agents/AgentHierarchyView").then((m) => ({ default: m.AgentHierarchyView }))
);
const FeatureSectionsView = React.lazy(() =>
  import("@/components/settings/FeatureSectionsView").then((m) => ({ default: m.FeatureSectionsView }))
);

export const App: React.FC = () => {
  const { activeNav, syncWithBackendEngine, toggleEmergencyStop } = useAksaStore();

  useEffect(() => {
    void syncWithBackendEngine();
  }, [syncWithBackendEngine]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === "q") {
        e.preventDefault();
        void toggleEmergencyStop(true);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [toggleEmergencyStop]);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#191918] text-[#ECECEB]">
      {/* Global Human-in-the-Loop Confirmation Modal */}
      <HITLApprovalModal />

      {/* Pane 1: Collapsible Left Navigation Sidebar */}
      <Sidebar />

      {/* Center + Right Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <TopHeader />

        <div className="flex-1 flex min-h-0 overflow-hidden">
          {/* Pane 2: Active Workspace / Agent Hierarchy / RAG / Telegram View with Suspense */}
          <Suspense fallback={<div className="flex-1 flex items-center justify-center text-sm text-[#8E8D8A]">Memuat modul...</div>}>
            {activeNav === "ruang_kerja" && <WorkspaceChatView />}
            {activeNav === "tim_agen" && <AgentHierarchyView />}
            {activeNav !== "ruang_kerja" && activeNav !== "tim_agen" && <FeatureSectionsView />}
          </Suspense>

          {/* Pane 3: Slide-Over File Artifact Inspector Drawer */}
          <ArtifactDrawer />
        </div>
      </div>
    </div>
  );
};

export default App;

