/**
 * Shared API response types for IntegrityDesk frontend.
 */

export interface Job {
  id: string;
  tenant_id: string;
  name: string;
  status: "pending" | "processing" | "completed" | "failed";
  threshold: number;
  webhook_url?: string;
  detection_modes?: string[];
  language_filters?: string[];
  created_at: string;
  updated_at?: string;
  completed_at?: string;
  submission_count?: number;
  result_count?: number;
}

export interface Submission {
  id: string;
  job_id: string;
  name: string;
  file_paths: string[];
  external_id?: string;
  created_at: string;
}

export interface SimilarityResult {
  id: string;
  job_id: string;
  submission_a_id: string;
  submission_b_id: string;
  score: number;
  risk_level: "critical" | "high" | "medium" | "low";
  engine_scores?: Record<string, number>;
  created_at: string;
}

export interface AIDetectionResult {
  id: string;
  job_id: string;
  submission_id: string;
  highest_score: number;
  verdict: string;
  pattern_scores?: Record<string, number>;
  evidence?: string[];
  created_at: string;
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: "admin" | "professor" | "student";
  tenant_id: string;
  last_login_at?: string;
}

export interface Tenant {
  id: string;
  name: string;
  tier: "free" | "basic" | "pro" | "enterprise";
}

export interface UsageMetric {
  tenant_id: string;
  period: string;
  jobs_processed: number;
  files_parsed: number;
  total_size_mb: number;
  compute_seconds: number;
  api_calls: number;
}

export interface ApiError {
  detail: string;
}

export interface BenchmarkDataset {
  id: string;
  name: string;
  available: boolean;
  runnable: boolean;
  status?: string;
  has_ground_truth?: boolean;
  is_demo?: boolean;
}

export interface BenchmarkResult {
  dataset: string;
  precision: number;
  recall: number;
  f1: number;
  true_positives: number;
  false_positives: number;
  false_negatives: number;
}

// ─── Job & Results ──────────────────────────────────────────────────────────

export type JobStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'analyzing';

export type ReviewStatus = 'unreviewed' | 'needs_review' | 'confirmed' | 'dismissed' | 'escalated';

export interface ToolScore {
  tool: string;
  score: number;
}

export interface MatchingBlock {
  clone_type?: string;
  similarity?: number;
  lines_a?: string;
  lines_b?: string;
}

export interface SimilarityResult {
  id: string;
  job_id: string;
  file_a: string;
  file_b: string;
  score: number;
  risk_level: 'critical' | 'high' | 'medium' | 'low';
  engine_scores?: Record<string, number>;
  features?: Record<string, number>;
  matching_blocks?: MatchingBlock[];
  verdict?: string;
  confidence?: number;
  review_status?: ReviewStatus;
  fusion_debug?: Record<string, unknown>;
  created_at: string;
}

export interface JobSummary {
  suspicious_pairs?: number;
  total_pairs?: number;
  flagged_count?: number;
  threshold?: number;
}

export interface WebAnalysisSubmission {
  name: string;
  match_count?: number;
}

export interface WebAnalysis {
  submissions?: WebAnalysisSubmission[];
}

export interface SubmissionRecord {
  [name: string]: string;
}

export interface Job {
  id: string;
  tenant_id: string;
  name: string;
  status: JobStatus;
  threshold: number;
  webhook_url?: string;
  detection_modes?: string[];
  language_filters?: string[];
  created_at: string;
  updated_at?: string;
  completed_at?: string;
  submission_count?: number;
  result_count?: number;
  results?: SimilarityResult[];
  review_status?: ReviewStatus;
  review_updated_at?: string;
  review_notes?: string;
  file_count?: number;
  assignment_name?: string;
  course_name?: string;
  submissions?: Record<string, unknown>;
  web_analysis?: WebAnalysis;
  summary?: JobSummary;
}

export interface PairResult {
  file_a?: string;
  file_b?: string;
  score?: number;
  _score?: number;
  matching_blocks?: MatchingBlock[];
  features?: Record<string, number>;
  fusion_debug?: Record<string, unknown>;
  verdict?: string;
  confidence?: number;
  code_a?: string;
  code_b?: string;
  _rank?: number;
  _confidence?: string;
  _evidence?: number;
  _status?: string;
  _key?: string;
  _denseRank?: number;
}

export interface ToolResult {
  tool: string;
  score: number;
}

export interface PairWithToolResults {
  label?: string;
  file_a?: string;
  file_b?: string;
  code_a?: string;
  code_b?: string;
  source_a?: string;
  source_b?: string;
  content_a?: string;
  content_b?: string;
  tool_results?: ToolResult[];
}

export interface SettingsResponse {
  professor_profile?: Record<string, unknown>;
  professor_profile_catalog?: Record<string, unknown>;
  applied_professor_profile?: Record<string, unknown>;
  default_threshold?: number;
  openai_api_key?: string;
  openai_base_url?: string;
  openai_model?: string;
  openai_api_key_configured?: boolean;
  anthropic_api_key?: string;
  anthropic_model?: string;
  anthropic_api_key_configured?: boolean;
  moss_user_id?: string;
  moss_user_id_configured?: boolean;
  embedding_runtime?: string;
  embedding_model?: string;
  embedding_server_url?: string;
  embedding_server_host?: string;
  embedding_server_port?: number;
  embedding_device?: string;
  embedding_batch_size?: number;
  batch_size?: number;
  max_file_size_mb?: number;
  max_files_per_job?: number;
  webhook_url?: string;
  source_scan_enabled?: boolean;
  source_scan_sites?: string[];
  audit_log_level?: string;
  audit_retention_days?: number;
  debug_mode?: boolean;
  [key: string]: unknown;
}
