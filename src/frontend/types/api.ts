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
