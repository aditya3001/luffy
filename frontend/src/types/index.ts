// API Response Types

export interface ApiResponse<T> {
  status: string;
  data?: T;
  message?: string;
  error?: string;
}

// Cluster Types
export interface ExceptionCluster {
  cluster_id: string;
  exception_type: string;
  signature: string;
  count: number;
  first_seen: string;
  last_seen: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  services: string[];
  has_rca: boolean;
  status: 'active' | 'skipped' | 'resolved';
  status_updated_at?: string;
  status_updated_by?: string;
  logger_path?: string;  // Logger path from log entry (e.g., com.company.service.ClassName)
}

export interface StackFrame {
  symbol: string;
  file: string;
  line: number;
  class?: string;
  method?: string;
}

export interface ClusterDetail extends ExceptionCluster {
  stack_trace: StackFrame[] | null;
  exception_message: string;
  sample_logs: LogEntry[];
}

export interface LogEntry {
  timestamp: string;
  level: string;
  message: string;
  service: string;
  metadata?: Record<string, any>;
}

// RCA Types
export interface RCAResult {
  cluster_id: string;
  root_cause: string;
  recommendations: string[];
  code_snippets?: CodeSnippet[];
  impact_analysis?: ImpactAnalysis;
  generated_at: string;
  confidence_score?: number;
}

export interface CodeSnippet {
  file: string;
  line: number;
  code: string;
  language?: string;
}

export interface ImpactAnalysis {
  affected_services: string[];
  user_impact: string;
  business_impact?: string;
}

export interface FeedbackRequest {
  cluster_id: string;
  rca_id: string;
  is_helpful: boolean;
  accuracy_rating?: number;
  comments?: string;
}

// Task Types
export interface PeriodicTask {
  enabled: boolean;
  interval_minutes?: number;
  cron?: string;
  description: string;
  last_modified: string | null;
  modified_by: string | null;
  last_run?: TaskExecution;
  next_run?: string;
}

export interface TaskExecution {
  timestamp: string;
  status: 'success' | 'failed' | 'skipped';
  duration?: number;
  result?: any;
}

export interface TaskConfig {
  enabled?: boolean;
  interval_minutes?: number;
  cron?: string;
  modified_by?: string;
}

export interface TasksResponse {
  status: string;
  tasks: Record<string, PeriodicTask>;
}

// Statistics Types
export interface SystemStats {
  total_clusters: number;
  active_clusters: number;
  active_exceptions: number;
  rca_generated: number;
  logs_processed: number;
  system_health: 'healthy' | 'degraded' | 'down';
  trends?: {
    clusters_change: number;
    rca_change: number;
  };
}

// Log Source Configuration Types
export interface LogSource {
  id: string;
  name: string;
  service_id: string;
  service_name: string;
  source_type: 'opensearch' | 'elasticsearch' | 'loki' | 'cloudwatch' | 'splunk';
  host: string;
  port: number;
  username?: string;
  password?: string;
  use_ssl: boolean;
  verify_certs: boolean;
  index_pattern: string;
  query_filter?: Record<string, any>;
  is_active: boolean;
  fetch_enabled: boolean;
  fetch_interval_minutes: number;
  connection_status: 'connected' | 'disconnected' | 'error' | 'unknown';
  last_connection_test?: string;
  last_fetch_at?: string;
  last_error?: string;
  active_exceptions_count: number;
  // Code Indexing Configuration
  code_indexing_enabled?: boolean;
  git_provider?: 'github' | 'gitlab';
  repository_url?: string;
  git_branch?: string;
  repository_owner?: string;
  repository_name?: string;
  token_status?: 'valid' | 'expired' | 'invalid' | 'not_configured';
  token_last_validated?: string;
  last_indexed_commit?: string;
  last_indexed_at?: string;
  indexing_status?: 'not_started' | 'in_progress' | 'completed' | 'failed';
  indexing_error?: string;
  created_at: string;
  updated_at: string;
}

export interface LogSourceConfig {
  name: string;
  service_id: string;
  source_type: LogSource['source_type'];
  host: string;
  port?: number;
  username?: string;
  password?: string;
  use_ssl?: boolean;
  verify_certs?: boolean;
  index_pattern: string;
  query_filter?: Record<string, any>;
  fetch_enabled?: boolean;
  fetch_interval_minutes?: number;
  // Note: Git configuration is now at Service level, not LogSource level
}

// Service Types
export interface Service {
  id: string;
  name: string;
  description?: string;
  version?: string;
  is_active: boolean;
  
  // Git Configuration (Clean Architecture)
  use_api_mode?: boolean;           // True: API mode, False: Local mode
  repository_url?: string;           // Git repository URL
  git_provider?: 'github' | 'gitlab';  // Git provider (bitbucket not yet supported)
  git_branch?: string;               // Branch name
  git_repo_path?: string;            // Local path (Local mode only)
  access_token?: string;             // Access token (never returned from API)
  
  // Processing Configuration
  log_processing_enabled?: boolean;
  log_fetch_interval_minutes?: number;
  rca_generation_enabled?: boolean;
  rca_generation_interval_minutes?: number;
  code_indexing_interval_hours?: number;
  
  // Status Tracking
  last_log_fetch?: string;
  last_rca_generation?: string;
  last_code_indexing?: string;
  last_indexed_commit?: string;
  
  // Statistics
  log_sources_count: number;
  active_exceptions_count: number;
  
  // Timestamps
  created_at: string;
  updated_at: string;
}

// Filter Types
export interface ClusterFilters {
  search?: string;
  severity?: ExceptionCluster['severity'][];
  status?: ExceptionCluster['status'] | 'all';
  services?: string[];
  dateRange?: [string, string];
}

// Pagination
export interface PaginationParams {
  page: number;
  pageSize: number;
  total?: number;
}
