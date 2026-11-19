export type NavSection =
  | "ruang_kerja"
  | "tim_agen"
  | "aplikasi"
  | "keahlian"
  | "pengetahuan_rag"
  | "telegram"
  | "izin_pc"
  | "pengaturan";

export type ThemeMode = "dark" | "light" | "system";
export type ResolvedTheme = "dark" | "light";
export type UIDensityMode = "comfortable" | "compact";
export type ModelSelectionMode = "auto" | "manual";

export type ProviderTokenStatus =
  | "not_connected"
  | "token_saved"
  | "needs_check"
  | "connected"
  | "connection_failed";

export type WorkspaceFolderStatus =
  | "accessible"
  | "read_only"
  | "not_found"
  | "permission_denied"
  | "unavailable";

export type ModelProvider =
  | "openai"
  | "anthropic"
  | "gemini"
  | "deepseek"
  | "openrouter"
  | "groq"
  | "ollama"
  | "lmstudio";

export interface AgentNodeConfig {
  id: string;
  team_id: string;
  parent_id: string | null;
  name: string;
  role_title: string;
  description: string;
  avatar_icon: string;
  tier_level: number;
  provider: ModelProvider;
  model_id: string;
  model_selection_mode?: ModelSelectionMode;
  temperature: number;
  max_tokens: number;
  system_prompt: string;
  tool_categories: string[];
  position_x: number;
  position_y: number;
}

export interface AgentTeam {
  id: string;
  name: string;
  description: string;
  is_default: boolean;
  agents: AgentNodeConfig[];
}

export interface WorkspaceFolderPermissionsGranular {
  list_files: boolean;
  read_content: boolean;
  create_files: boolean;
  modify_files: boolean;
  move_files: boolean;
  delete_files: boolean;
  execute_programs: boolean;
}

export interface WorkspaceFolder {
  id: string;
  name: string;
  folder_path: string;
  allow_read: boolean;
  allow_write: boolean;
  allow_execute: boolean;
  auto_rag_sync: boolean;
  last_indexed_at?: string | null;
  granular_permissions?: WorkspaceFolderPermissionsGranular;
  folder_status?: WorkspaceFolderStatus;
  folder_status_label?: string;
  recovery_hint?: string | null;
}

export interface WorkspaceFolderInspection {
  folder_path: string;
  name: string;
  folder_status: WorkspaceFolderStatus;
  folder_status_label: string;
  is_valid_directory: boolean;
  readable: boolean;
  writable: boolean;
  recovery_hint: string | null;
}

export interface ProviderStatusDetail {
  id: ModelProvider;
  name: string;
  is_local: boolean;
  configured: boolean;
  has_saved_token: boolean;
  online: boolean;
  token_status: ProviderTokenStatus;
  api_key_masked?: string;
  last_test_ok?: boolean | null;
  last_tested_at?: string | null;
  last_test_message?: string | null;
  installed_models: string[];
}

export interface FileArtifact {
  id: string;
  name: string;
  file_path: string;
  file_type: "xlsx" | "docx" | "pptx" | "pdf" | "py" | "other";
  size_label: string;
  created_by_agent: string;
  created_at_label: string;
  summary: string;
  artifact_category?: "final" | "temporary" | "log";
}

export interface ExecutionStep {
  id: string;
  agent_name: string;
  agent_role: string;
  provider: ModelProvider;
  model_id: string;
  action_label: string;
  detail: string;
  status: "completed" | "running" | "pending";
  tokens_used: number;
  tokens_saved: number;
}

export interface ChatMessage {
  id: string;
  sender_role: "user" | "supervisor";
  sender_name: string;
  content: string;
  timestamp_label: string;
  execution_steps?: ExecutionStep[];
  artifacts?: FileArtifact[];
}

export interface EngineHealth {
  online: boolean;
  version: string;
  ollama_online: boolean;
  ollama_models: string[];
  telegram_connected: boolean;
  telegram_bot_username: string | null;
}

export interface HITLApprovalItem {
  id: string;
  tool_name: string;
  risk_level: "low" | "medium" | "high";
  title_id: string;
  description_id: string;
  target_path?: string | null;
  agent_name: string;
  status: "pending" | "approved" | "rejected";
  created_at: string;
}

export interface MCPServerItem {
  id: string;
  name: string;
  transport: string;
  command: string;
  args: string[];
  enabled: boolean;
  description_id: string;
  discovered_tools: string[];
}

export interface DesktopApp {
  id: string;
  platform: string;
  platform_app_id: string;
  display_name: string;
  publisher?: string | null;
  version?: string | null;
  install_location?: string | null;
  install_scope: string;
  is_installed: boolean;
  is_running: boolean;
  is_connected?: boolean;
  category_label?: string;
  available_adapters: string[];
  detection_sources: string[];
}

export interface CapabilityStatus {
  capability_id: string;
  display_name: string;
  description: string;
  scope_type: string;
  requires_hitl: boolean;
  os_status:
    | "UNSUPPORTED"
    | "NOT_REQUESTED"
    | "NEEDS_USER_ACTION"
    | "PENDING"
    | "GRANTED"
    | "DENIED"
    | "REVOKED"
    | "ERROR";
  aksa_status: "granted" | "not_granted" | "automatic_sandbox";
  revocation_guide?: string;
  grant_id?: string | null;
  granted_at?: string | null;
}

export interface SkillItem {
  id: string;
  skill_id: string;
  display_name: string;
  publisher: string;
  installed_version: string;
  package_hash: string;
  trust_level: "curated" | "verified_publisher" | "community_reviewed" | "unreviewed" | "blocked";
  enabled: boolean;
  installed_at: string;
}

export interface CuratedSkill {
  id: string;
  display_name: string;
  version: string;
  publisher: string;
  description: string;
  trust_level: string;
  capabilities: string[];
  has_scripts: boolean;
  has_network: boolean;
  scripts: string[];
  instructions_preview: string;
}


