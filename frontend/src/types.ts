/** Shared API types mirroring the backend Pydantic schemas. */

export type RepoStatus =
  | "queued"
  | "cloning"
  | "scanning"
  | "parsing"
  | "ready"
  | "failed";

export interface SecretFinding {
  rule_id: string;
  severity: "critical" | "high" | "medium" | "low";
  file: string;
  line: number;
  preview: string;
}

export interface DependencyNode {
  id: string;
  path: string;
  language: string;
  loc: number;
  imports: string[];
  symbols: string[];
}

export interface DependencyEdge {
  source: string;
  target: string;
  symbol: string | null;
}

export interface DependencyGraph {
  nodes: DependencyNode[];
  edges: DependencyEdge[];
  external_packages: string[];
}

export interface RepositorySummary {
  id: string;
  url: string;
  name: string;
  branch: string | null;
  default_branch: string | null;
  head_commit: string | null;
  status: RepoStatus;
  depth: number;
  file_count: number;
  total_loc: number;
  languages: Record<string, number>;
  secret_findings: SecretFinding[];
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface RepositoryDetail extends RepositorySummary {
  dep_graph: DependencyGraph | null;
}

export type VaultState = "locked" | "unlocked";

export interface VaultStatus {
  state: VaultState;
  kdf_algorithm: string;
  pbkdf2_iterations: number;
  argon2_configured: boolean;
  key_count: number;
  active_key_count: number;
}

export interface ProviderKey {
  id: string;
  provider_id: string;
  label: string;
  fingerprint: string;
  status: "active" | "invalid" | "revoked";
  masked_hint: string;
  last_verified_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProviderRuntimeStatus {
  provider_id: string;
  display_name: string;
  base_url: string;
  default_model: string;
  supported_models: string[];
  max_tokens_limit: number;
  priority: number;
  key_configured: boolean;
  key_fingerprint: string | null;
  key_status: "active" | "invalid" | "revoked" | null;
  circuit: "closed" | "open" | "half_open";
  requests_in_window: number;
  rate_limit_max: number;
  rate_limit_window_seconds: number;
  ewma_latency_ms: number | null;
  total_requests: number;
  failed_requests: number;
  last_error: string | null;
}

export interface ProviderCatalog {
  vault_config: Record<string, unknown>;
  providers: ProviderRuntimeStatus[];
}

export interface UsageSummary {
  total_requests: number;
  ok_requests: number;
  failed_requests: number;
  prompt_tokens: number;
  completion_tokens: number;
  avg_latency_ms: number;
  by_provider: Record<string, Record<string, number>>;
}

export type JobStatus =
  | "queued"
  | "running"
  | "planning"
  | "architecting"
  | "coding"
  | "reviewing"
  | "validating"
  | "patching"
  | "completed"
  | "failed"
  | "cancelled";

export type AgentRole =
  | "planner"
  | "architect"
  | "coder"
  | "reviewer"
  | "patcher"
  | "validator";

export interface SwarmJob {
  id: string;
  repository_id: string;
  task: string;
  status: JobStatus;
  current_agent: string | null;
  repair_iteration: number;
  max_repair_iterations: number;
  config: Record<string, unknown>;
  token_usage: { prompt_tokens: number; completion_tokens: number; requests: number };
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface FileEditArtifact {
  path: string;
  action: "create" | "modify" | "delete";
  content: string;
}

export interface SwarmJobDetail extends SwarmJob {
  plan: Record<string, unknown> | null;
  architecture: Record<string, unknown> | null;
  review: Record<string, unknown> | null;
  validation: Record<string, unknown> | null;
  edits: FileEditArtifact[];
  diff: string | null;
  repository_name: string | null;
}

export interface SwarmEvent {
  id?: number;
  type: string;
  agent?: string | null;
  data: Record<string, unknown>;
  created_at?: string | null;
}

export interface DiffHunk {
  old_start: number;
  new_start: number;
  old_lines: [number, string][];
  new_lines: [number, string][];
}

export interface DiffFile {
  path: string;
  additions: number;
  deletions: number;
  is_new: boolean;
  is_deleted: boolean;
  is_binary: boolean;
  hunks: DiffHunk[];
}

export interface DiffSummary {
  job_id: string;
  files: DiffFile[];
  additions: number;
  deletions: number;
  raw: string;
}

export interface DashboardStats {
  jobs: number;
  completed_jobs: number;
  active_jobs: number;
  repositories: number;
}
