import { describe, it, expect, beforeEach } from "vitest";
import { useAksaStore } from "../stores/useAksaStore";
import {
  computeAutoHierarchyLayout,
  extractFolderDisplayName,
  formatPermissionStatusLabel,
  formatProviderTokenStatus,
  formatWorkspaceFolderStatus,
  getHumanModelInfo,
  TOOL_CATEGORY_LABELS,
  wouldCreateAgentCycle,
} from "../lib/utils";

describe("useAksaStore & Siklus 16 UX/UI state management tests", () => {
  beforeEach(() => {
    useAksaStore.setState({
      activeNav: "ruang_kerja",
      selectedAgentId: null,
      activeWorkspaceId: "",
      isExecuting: false,
      emergencyStopActive: false,
      themeMode: "dark",
      resolvedTheme: "dark",
      uiDensity: "comfortable",
      reducedMotion: false,
    });
  });

  it("initializes with default team and navigation state", () => {
    const state = useAksaStore.getState();

    expect(state.teams).toBeDefined();
    expect(state.teams.length).toBeGreaterThan(0);
    expect(state.teams[0].id).toBe("team_nusantara_default");
    expect(state.activeNav).toBe("ruang_kerja");
    expect(state.isExecuting).toBe(false);
    expect(state.themeMode).toBe("dark");
    expect(state.resolvedTheme).toBe("dark");
  });

  it("updates navigation item correctly", () => {
    const { setActiveNav } = useAksaStore.getState();

    setActiveNav("tim_agen");
    expect(useAksaStore.getState().activeNav).toBe("tim_agen");

    setActiveNav("pengaturan");
    expect(useAksaStore.getState().activeNav).toBe("pengaturan");

    setActiveNav("pengetahuan_rag");
    expect(useAksaStore.getState().activeNav).toBe("pengetahuan_rag");
  });

  it("switches active workspace", () => {
    const { setActiveWorkspace } = useAksaStore.getState();

    setActiveWorkspace("ws_project_alpha");
    expect(useAksaStore.getState().activeWorkspaceId).toBe("ws_project_alpha");

    setActiveWorkspace("ws_finance_2026");
    expect(useAksaStore.getState().activeWorkspaceId).toBe("ws_finance_2026");
  });

  it("toggles sidebar collapsed state", () => {
    const initial = useAksaStore.getState().isSidebarCollapsed;
    const { toggleSidebar } = useAksaStore.getState();

    toggleSidebar();
    expect(useAksaStore.getState().isSidebarCollapsed).toBe(!initial);

    toggleSidebar();
    expect(useAksaStore.getState().isSidebarCollapsed).toBe(initial);
  });

  it("manages selected agent selection", () => {
    const { selectAgent } = useAksaStore.getState();

    selectAgent("agt_spesialis_office");
    expect(useAksaStore.getState().selectedAgentId).toBe("agt_spesialis_office");

    selectAgent(null);
    expect(useAksaStore.getState().selectedAgentId).toBeNull();
  });

  it("maps technical permission enums to everyday Bahasa Indonesia status labels", () => {
    expect(formatPermissionStatusLabel("GRANTED").label).toBe("Izin diberikan");
    expect(formatPermissionStatusLabel("DENIED").label).toBe("Akses ditolak");
    expect(formatPermissionStatusLabel("NEEDS_USER_ACTION").label).toBe("Memerlukan tindakan Anda");
    expect(formatPermissionStatusLabel("automatic_sandbox").label).toBe("Dilindungi otomatis");
    expect(formatPermissionStatusLabel("UNSUPPORTED").label).toBe(
      "Tidak tersedia pada perangkat ini"
    );
    expect(TOOL_CATEGORY_LABELS.rag_search).toBe("Pencarian dalam Dokumen");
  });

  it("updates granular folder permissions without automatically enabling high-risk delete or execute", async () => {
    useAksaStore.setState({
      workspaces: [
        {
          id: "ws_test_1",
          name: "Dokumen Kerja",
          folder_path: "/tmp/dokumen",
          allow_read: true,
          allow_write: false,
          allow_execute: false,
          auto_rag_sync: true,
        },
      ],
      activeWorkspaceId: "ws_test_1",
    });

    const { updateWorkspacePermissions, addSubAgent } = useAksaStore.getState();
    updateWorkspacePermissions("ws_test_1", {
      granular_permissions: {
        list_files: true,
        read_content: true,
        create_files: true,
        modify_files: false,
        move_files: false,
        delete_files: false,
        execute_programs: false,
      },
    });

    const ws = useAksaStore.getState().workspaces[0];
    expect(ws.allow_read).toBe(true);
    expect(ws.allow_write).toBe(true);
    expect(ws.allow_execute).toBe(false);
    expect(ws.granular_permissions?.delete_files).toBe(false);
    expect(ws.granular_permissions?.execute_programs).toBe(false);

    // Adding a supporting agent must not automatically inherit high-risk permissions
    const parent = useAksaStore.getState().teams[0].agents[0];
    const created = await addSubAgent(parent);
    expect(created).toBeDefined();
    expect(created.tool_categories).toEqual(["filesystem"]);
  });

  it("supports dark, light, and system theme switching and reduced motion (Siklus 16 Section 2 & 7)", () => {
    const { setThemeMode, syncSystemTheme, setUiDensity, setReducedMotion } =
      useAksaStore.getState();

    setThemeMode("light");
    expect(useAksaStore.getState().themeMode).toBe("light");
    expect(useAksaStore.getState().resolvedTheme).toBe("light");

    setThemeMode("system");
    syncSystemTheme(false);
    expect(useAksaStore.getState().themeMode).toBe("system");
    expect(useAksaStore.getState().resolvedTheme).toBe("light");

    syncSystemTheme(true);
    expect(useAksaStore.getState().resolvedTheme).toBe("dark");

    setThemeMode("dark");
    expect(useAksaStore.getState().resolvedTheme).toBe("dark");

    setUiDensity("compact");
    expect(useAksaStore.getState().uiDensity).toBe("compact");

    setReducedMotion(true);
    expect(useAksaStore.getState().reducedMotion).toBe(true);
  });

  it("validates agent hierarchy, rejects circular dependencies, and reassigns sub-agents on deletion (Siklus 16 Section 3)", async () => {
    const { addSubAgent, reparentAgent, deleteAgentNode } = useAksaStore.getState();
    const root = useAksaStore.getState().teams[0].agents.find((a) => a.parent_id === null)!;
    expect(root).toBeDefined();

    // Create child B under Root, and grandchild C under B
    const childB = await addSubAgent(root, { name: "Agen B" });
    const grandChildC = await addSubAgent(childB, { name: "Sub-Agen C" });

    expect(childB.parent_id).toBe(root.id);
    expect(grandChildC.parent_id).toBe(childB.id);
    expect(grandChildC.tier_level).toBe(childB.tier_level + 1);

    // Circular dependency check: B cannot have C (its own descendant) as parent
    const currentAgents = useAksaStore.getState().teams[0].agents;
    expect(wouldCreateAgentCycle(currentAgents, childB.id, grandChildC.id)).toBe(true);
    expect(wouldCreateAgentCycle(currentAgents, childB.id, childB.id)).toBe(true);
    expect(wouldCreateAgentCycle(currentAgents, grandChildC.id, root.id)).toBe(false);

    const cycleRes = await reparentAgent(childB.id, grandChildC.id);
    expect(cycleRes.ok).toBe(false);
    expect(cycleRes.error).toContain("Relasi melingkar");

    // Root cannot be reparented
    const rootReparentRes = await reparentAgent(root.id, childB.id);
    expect(rootReparentRes.ok).toBe(false);

    // Deleting middle agent B must reassign grandchild C directly under Root (no orphan nodes)
    await deleteAgentNode(childB.id);
    const updatedAgents = useAksaStore.getState().teams[0].agents;
    expect(updatedAgents.find((a) => a.id === childB.id)).toBeUndefined();
    const survivingC = updatedAgents.find((a) => a.id === grandChildC.id);
    expect(survivingC).toBeDefined();
    expect(survivingC?.parent_id).toBe(root.id);

    // Layout computation positions root at tier 0 and children below with generous spacing
    const layout = computeAutoHierarchyLayout(updatedAgents);
    expect(layout[root.id].tier_level).toBe(0);
    expect(layout[root.id].position_y).toBe(30);
    expect(layout[grandChildC.id].position_y).toBeGreaterThanOrEqual(360);
    const tier1Ids = Object.keys(layout).filter((id) => layout[id].tier_level === 1);
    if (tier1Ids.length >= 2) {
      const gap = Math.abs(layout[tier1Ids[1]].position_x - layout[tier1Ids[0]].position_x);
      expect(gap).toBeGreaterThanOrEqual(420);
    }
  });

  it("supports both automatic and manual model selection with human-friendly model metadata (Siklus 16 Section 4)", async () => {
    const { updateAgentConfig } = useAksaStore.getState();
    const officeAgent = useAksaStore
      .getState()
      .teams[0].agents.find((a) => a.id === "agt_spesialis_office")!;

    await updateAgentConfig(officeAgent.id, {
      provider: "anthropic",
      model_id: "claude-sonnet-5-5",
      model_selection_mode: "manual",
    });

    const updated = useAksaStore
      .getState()
      .teams[0].agents.find((a) => a.id === "agt_spesialis_office")!;
    expect(updated.provider).toBe("anthropic");
    expect(updated.model_id).toBe("claude-sonnet-5-5");
    expect(updated.model_selection_mode).toBe("manual");

    const info = getHumanModelInfo("anthropic", "claude-sonnet-5-5");
    expect(info.friendlyName).toBe("Claude Sonnet 5.5");
    expect(info.supportsToolCalling).toBe(true);
    expect(info.contextWindowLabel).toContain("200K");
  });

  it("distinguishes all 5 provider token statuses and workspace folder statuses (Siklus 16 Section 5 & 6)", () => {
    expect(formatProviderTokenStatus("not_connected").label).toBe("Belum dihubungkan");
    expect(formatProviderTokenStatus("token_saved").label).toBe("Token tersimpan");
    expect(formatProviderTokenStatus("needs_check").label).toBe("Perlu diperiksa");
    expect(formatProviderTokenStatus("connected").label).toBe("Terhubung");
    expect(formatProviderTokenStatus("connection_failed").label).toBe("Koneksi gagal");

    expect(formatWorkspaceFolderStatus("accessible").label).toBe("Dapat diakses");
    expect(formatWorkspaceFolderStatus("read_only").label).toBe("Hanya baca (Read-only)");
    expect(formatWorkspaceFolderStatus("not_found").label).toBe("Tidak ditemukan");
    expect(formatWorkspaceFolderStatus("permission_denied").label).toBe("Izin ditolak");
    expect(formatWorkspaceFolderStatus("unavailable").label).toBe("Tidak tersedia");

    expect(extractFolderDisplayName("/Users/budi/Documents/Laporan Keuangan 2026")).toBe(
      "Laporan Keuangan 2026"
    );
    expect(extractFolderDisplayName("C:\\Users\\Sari\\Proyek Dokumen\\Arsip")).toBe("Arsip");
  });

  it("manages initial application loading and database hydration state", async () => {
    useAksaStore.setState({ isAppReady: false });
    const { isAppReady, setAppReady, syncWithBackendEngine } = useAksaStore.getState();

    expect(isAppReady).toBe(false);
    setAppReady(true);
    expect(useAksaStore.getState().isAppReady).toBe(true);

    useAksaStore.setState({ isAppReady: false });
    await syncWithBackendEngine();
    expect(useAksaStore.getState().isAppReady).toBe(true);
    expect(useAksaStore.getState().initProgress).toBe(100);
    expect(useAksaStore.getState().initStage.database).toBe("done");
  });
});
