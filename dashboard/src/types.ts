export type PipelineStatus = 'idle' | 'running' | 'done' | 'failed' | 'error' | 'killed';
export type SystemState = 'running' | 'just-completed' | 'error' | 'idle';
export type HealthStatus = 'healthy' | 'degraded' | 'unhealthy';

export interface Agent {
  num: number;
  name: string;
  codename: string;
  short?: boolean;
}

export interface PulseResponse {
  status: PipelineStatus;
  running: boolean;
  stage: string;
  stage_num: number;
  topic: string;
  started_at: string | null;
  finished_at: string | null;
  analytics_running: boolean;
  queue_depth: number;
  errors_24h: number;
  health: HealthStatus;
  last_cost_usd: number | null;
}

export interface SummarySignal {
  label: string;
  value: string;
  type: 'info' | 'success' | 'warning' | 'error' | 'neutral';
}

export interface DashboardResponse {
  summary?: { signals: SummarySignal[] };
  performance?: Record<string, unknown>;
  content?: Record<string, unknown>;
  audience?: Record<string, unknown>;
  config?: Record<string, unknown>;
  analytics?: Record<string, unknown>;
}

export interface LastRunData {
  topic: string;
  status: string;
  started_at: string;
  finished_at: string;
  elapsed_seconds: number;
  cost_usd: number | null;
  stages_completed: number;
  youtube_id?: string;
}

export interface SummarySignalWithRaw extends SummarySignal {
  raw?: Record<string, unknown>;
}

export interface RunDetail {
  topic: string;
  status: string;
  stage_timings: Record<string, number>;
  costs: {
    usd_total: number;
    per_stage: Record<string, number>;
    per_service: Record<string, number>;
  };
  tokens: {
    input: number;
    output: number;
    per_model: Record<string, number>;
  };
  quality: {
    hook_scores?: Record<string, unknown>;
    script_doctor?: Record<string, number>;
    fact_verification?: string;
    compliance?: { risk_level: string; flag_count: number };
    qa_tier1?: Record<string, unknown>;
    qa_tier2_sync_pct?: number;
    seo_score?: number;
    predictive_score?: number;
  };
  output: {
    youtube_url?: string;
    youtube_id?: string;
    duration_s?: number;
    word_count?: number;
    scene_count?: number;
    file_size_mb?: number;
  };
  agent_performance: {
    agent: string;
    elapsed_s: number;
    sla_s: number;
    model: string;
    status: string;
  }[];
  doctor_interventions: Record<string, unknown>[];
}

export interface QueueItem {
  id: string;
  topic: string;
  score: number;
  status: string;
  source: string;
  [k: string]: unknown;
}

export interface ScheduleEntry {
  day: string;
  time_utc: string;
  job: string;
}

export interface CostEvent {
  usd_total: number;
  tokens: Record<string, number>;
}

// ── Observability types ───────────────────────────────────────────────────────

export interface ErrorEntry {
  timestamp: string; agent: string; error_type: string;
  error_message: string; severity: string; count: number;
  stack_trace?: string; dedup_key: string;
}
export interface AgentStat {
  agent: string; calls: number; avg_latency: number;
  p95_latency: number; success_rate: number; sla_breach_rate: number;
  avg_input_tokens: number; avg_output_tokens: number;
}

// ── Tuning types ──────────────────────────────────────────────────────────────

export type MaturityLevel = 'early' | 'emerging' | 'established' | 'mature'
export type ConfidenceLevel = 'strong' | 'moderate' | 'directional' | 'weak'

export interface ParamBound {
  key: string
  label: string
  description: string
  group: 'long_form' | 'short_speed' | 'short_voice' | 'short_timing'
  groupLabel: string
  min: number
  max: number
  default: number
  step: number
  unit?: string
  brandRef?: string
  brandThreshold?: number
}

export interface Override {
  key: string
  value: number
}

export interface OverrideHistoryEntry {
  key: string
  action: 'approve' | 'revert'
  value: number | null
  previous_value: number | null
  timestamp: string
  approved_by?: string
}

export interface CorrelationLayer {
  status: string
  layer: number
  reason: string
  confidence: number
  results?: Record<string, unknown>
  tests_run?: number
  tests_significant?: number
}

export interface TopicRankingEntry {
  topic: string
  long_count: number
  short_count: number
  avg_long_views: number | null
  avg_long_retention: number | null
  avg_long_subs: number | null
  avg_short_views: number | null
}

export interface TuningRecommendation {
  parameter_key: string
  suggested_value: number
  confidence: ConfidenceLevel
  evidence_layers: number[]
  interpretation: string
  quality_score?: number
}

export interface CorrelationResults {
  generated_at?: string
  maturity?: MaturityLevel
  maturity_description?: string
  video_count?: number
  short_count?: number
  layers?: Record<string, CorrelationLayer>
  active_layer_count?: number
  recommendations?: TuningRecommendation[]
}

export interface TuningData {
  overrides: Override[]
  bounds: Record<string, { min: number; max: number }>
  defaults: Record<string, number>
  history: OverrideHistoryEntry[]
  correlation: CorrelationResults
}

// ── Setup Wizard types ───────────────────────────────────────────────────────

export interface SetupKeyStatus {
  key: string
  label: string
  required: boolean
  help: string
  category: string
  configured: boolean
}

export interface SetupProfile {
  name: string
  description: string
}

export interface SetupStatus {
  keys: SetupKeyStatus[]
  profile: string
  available_profiles: SetupProfile[]
  providers: Record<string, string>
  available_providers: Record<string, string[]>
  setup_complete: boolean
}

export interface SetupValidation {
  key: string
  valid: boolean
  error: string
  info?: Record<string, unknown>
}
