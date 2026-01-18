import axios from 'axios';
import type {
  ExceptionCluster,
  ClusterDetail,
  RCAResult,
  FeedbackRequest,
  TasksResponse,
  TaskConfig,
  SystemStats,
  LogSource,
  LogSourceConfig,
  Service,
} from '@/types';

// Create axios instance
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});
// Request interceptor
api.interceptors.request.use(
  (config) => {
    // Add auth token if available
    const token = localStorage.getItem('auth_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Handle unauthorized
      localStorage.removeItem('auth_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Cluster API
export const clusterAPI = {
  list: async (status: string = 'active', serviceId?: string, logSourceId?: string, timeFilter?: string): Promise<ExceptionCluster[]> => {
    const params = new URLSearchParams({ status });
    if (serviceId) params.append('service_id', serviceId);
    if (logSourceId) params.append('log_source_id', logSourceId);
    if (timeFilter) params.append('time_filter', timeFilter);
    const response = await api.get(`/clusters?${params}`);
    return response.data.clusters || [];
  },

  get: async (clusterId: string): Promise<ClusterDetail> => {
    const response = await api.get(`/clusters/${clusterId}`);
    return response.data.cluster;
  },

  search: async (query: string): Promise<ExceptionCluster[]> => {
    const response = await api.get(`/clusters?search=${encodeURIComponent(query)}`);
    return response.data.clusters || [];
  },

  skip: async (clusterId: string): Promise<void> => {
    await api.post(`/clusters/${clusterId}/skip`);
  },

  resolve: async (clusterId: string): Promise<void> => {
    await api.post(`/clusters/${clusterId}/resolve`);
  },

  reactivate: async (clusterId: string): Promise<void> => {
    await api.post(`/clusters/${clusterId}/reactivate`);
  },
};

// RCA API
export const rcaAPI = {
  get: async (clusterId: string): Promise<RCAResult | null> => {
    try {
      const response = await api.get(`/rca/${clusterId}`);
      return response.data.rca;
    } catch (error: any) {
      if (error.response?.status === 404) {
        return null;
      }
      throw error;
    }
  },

  generate: async (clusterId: string): Promise<{ task_id: string; status: string }> => {
    const response = await api.post('/rca/generate', { cluster_id: clusterId });
    return response.data;
  },

  submitFeedback: async (feedback: FeedbackRequest): Promise<void> => {
    await api.post('/feedback', feedback);
  },
};

// Task API
export const taskAPI = {
  list: async (): Promise<TasksResponse> => {
    const response = await api.get('/tasks');
    return response.data;
  },

  get: async (taskName: string): Promise<any> => {
    const response = await api.get(`/tasks/${taskName}`);
    return response.data.task;
  },

  enable: async (taskName: string): Promise<void> => {
    await api.post(`/tasks/${taskName}/enable`);
  },

  disable: async (taskName: string): Promise<void> => {
    await api.post(`/tasks/${taskName}/disable`);
  },

  update: async (taskName: string, config: TaskConfig): Promise<void> => {
    await api.put(`/tasks/${taskName}`, config);
  },

  reset: async (taskName: string): Promise<void> => {
    await api.post(`/tasks/${taskName}/reset`);
  },
};

// Statistics API
export const statsAPI = {
  get: async (serviceId?: string, timeFilter?: string): Promise<SystemStats> => {
    const params: any = {};
    if (serviceId) params.service_id = serviceId;
    if (timeFilter) params.time_filter = timeFilter;
    return api.get('/stats', { params }).then((res) => res.data);
  },

  getTrends: async (days: number = 7, serviceId?: string, logSourceId?: string, timeFilter?: string): Promise<{ date: string; full_date: string; exceptions: number }[]> => {
    const params: any = { days };
    if (serviceId) params.service_id = serviceId;
    if (logSourceId) params.log_source_id = logSourceId;
    if (timeFilter) params.time_filter = timeFilter;
    const response = await api.get('/trends', { params });
    return response.data.trends || response.data;
  },

  getServiceStats: async (limit: number = 10): Promise<{ service: string; count: number; clusters: number }[]> => {
    const response = await api.get(`/stats/services?limit=${limit}`);
    return response.data;
  },

  getSeverityDistribution: async (): Promise<{ severity: string; count: number }[]> => {
    const response = await api.get('/stats/severity');
    return response.data;
  },
};

// Services API
export const servicesAPI = {
  list: async (): Promise<Service[]> => {
    const response = await api.get('/services');
    return response.data;
  },

  get: async (serviceId: string): Promise<Service> => {
    const response = await api.get(`/services/${serviceId}`);
    return response.data;
  },

  create: async (service: Partial<Service>): Promise<Service> => {
    const response = await api.post('/services', service);
    return response.data;
  },

  update: async (serviceId: string, service: Partial<Service>): Promise<Service> => {
    const response = await api.put(`/services/${serviceId}`, service);
    return response.data;
  },

  delete: async (serviceId: string): Promise<void> => {
    await api.delete(`/services/${serviceId}`);
  },

  listLogSources: async (serviceId: string): Promise<LogSource[]> => {
    const response = await api.get(`/services/${serviceId}/log-sources`);
    return response.data;
  },

  createLogSource: async (serviceId: string, logSource: any): Promise<any> => {
    const response = await api.post(`/services/${serviceId}/log-sources`, logSource);
    return response.data;
  },

  updateLogSource: async (serviceId: string, logSourceId: string, logSource: any): Promise<any> => {
    const response = await api.put(`/services/${serviceId}/log-sources/${logSourceId}`, logSource);
    return response.data;
  },

  deleteLogSource: async (serviceId: string, logSourceId: string): Promise<void> => {
    await api.delete(`/services/${serviceId}/log-sources/${logSourceId}`);
  },

  testLogSource: async (serviceId: string, logSourceId: string): Promise<any> => {
    const response = await api.post(`/services/${serviceId}/log-sources/${logSourceId}/test`);
    return response.data;
  },

  toggleLogSource: async (serviceId: string, logSourceId: string, enabled: boolean): Promise<any> => {
    const response = await api.post(`/services/${serviceId}/log-sources/${logSourceId}/toggle?enabled=${enabled}`);
    return response.data;
  },

  // Manual task triggers
  triggerLogFetch: async (serviceId: string): Promise<{ message: string; task_id: string; service_id: string }> => {
    const response = await api.post(`/services/${serviceId}/trigger-log-fetch`);
    return response.data;
  },

  triggerRCA: async (serviceId: string): Promise<{ message: string; task_id: string; service_id: string }> => {
    const response = await api.post(`/services/${serviceId}/trigger-rca`);
    return response.data;
  },

  triggerCodeIndexing: async (serviceId: string): Promise<{ message: string; task_id: string; service_id: string; repository_path: string; branch: string }> => {
    const response = await api.post(`/services/${serviceId}/trigger-code-indexing`);
    return response.data;
  },

  toggleLogProcessing: async (serviceId: string, enabled: boolean): Promise<{ message: string; service_id: string; service_name: string; log_processing_enabled: boolean }> => {
    const response = await api.post(`/services/${serviceId}/toggle-log-processing?enabled=${enabled}`);
    return response.data;
  },
};

// Task Management API
export const taskManagementAPI = {
  getOverview: async (): Promise<any> => {
    const response = await api.get('/task-management/overview');
    return response.data;
  },

  listServiceTasks: async (): Promise<any[]> => {
    const response = await api.get('/task-management/services');
    return response.data;
  },

  getServiceTasks: async (serviceId: string): Promise<any> => {
    const response = await api.get(`/task-management/services/${serviceId}`);
    return response.data;
  },

  updateServiceTasks: async (serviceId: string, config: any): Promise<any> => {
    const response = await api.put(`/task-management/services/${serviceId}`, config);
    return response.data;
  },

  listLogSourceTasks: async (serviceId: string): Promise<any[]> => {
    const response = await api.get(`/task-management/services/${serviceId}/log-sources`);
    return response.data;
  },

  getLogSourceTasks: async (logSourceId: string): Promise<any> => {
    const response = await api.get(`/task-management/log-sources/${logSourceId}`);
    return response.data;
  },

  updateLogSourceTasks: async (logSourceId: string, config: any): Promise<any> => {
    const response = await api.put(`/task-management/log-sources/${logSourceId}`, config);
    return response.data;
  },

  toggleLogSourceFetch: async (logSourceId: string, enabled: boolean): Promise<any> => {
    const response = await api.post(`/task-management/log-sources/${logSourceId}/toggle?enabled=${enabled}`);
    return response.data;
  },

  enableAllServiceTasks: async (serviceId: string): Promise<any> => {
    const response = await api.post(`/task-management/services/${serviceId}/enable-all`);
    return response.data;
  },

  disableAllServiceTasks: async (serviceId: string): Promise<any> => {
    const response = await api.post(`/task-management/services/${serviceId}/disable-all`);
    return response.data;
  },
};

// Log Source API (Extended functionality)
export const logSourceAPI = {
  list: async (): Promise<LogSource[]> => {
    const response = await api.get('/log-sources');
    return response.data;
  },

  get: async (sourceId: string): Promise<LogSource> => {
    const response = await api.get(`/log-sources/${sourceId}`);
    return response.data;
  },

  create: async (config: LogSourceConfig): Promise<LogSource> => {
    const response = await api.post('/log-sources', config);
    return response.data;
  },

  update: async (sourceId: string, config: Partial<LogSourceConfig>): Promise<LogSource> => {
    const response = await api.put(`/log-sources/${sourceId}`, config);
    return response.data;
  },

  delete: async (sourceId: string): Promise<void> => {
    await api.delete(`/log-sources/${sourceId}`);
  },

  test: async (sourceId: string): Promise<{ success: boolean; message: string; details?: any; response_time_ms?: number }> => {
    const response = await api.post(`/log-sources/${sourceId}/test`);
    return response.data;
  },

  // Monitoring control
  controlMonitoring: async (sourceId: string, enabled: boolean, applyToAll: boolean = false): Promise<any> => {
    const response = await api.post(`/log-sources/${sourceId}/monitoring`, {
      enabled,
      apply_to_all: applyToAll
    });
    return response.data;
  },

  getMonitoringStatus: async (): Promise<any[]> => {
    const response = await api.get('/log-sources/monitoring/status');
    return response.data;
  },

  enableAllMonitoring: async (serviceId?: string): Promise<any> => {
    const params = serviceId ? `?service_id=${serviceId}` : '';
    const response = await api.post(`/log-sources/monitoring/enable-all${params}`);
    return response.data;
  },

  disableAllMonitoring: async (serviceId?: string): Promise<any> => {
    const url = serviceId 
      ? `/log-sources/monitoring/disable-all?service_id=${serviceId}`
      : '/log-sources/monitoring/disable-all';
    const response = await api.post(url);
    return response.data;
  },

  // Code indexing control
  triggerIndexing: async (sourceId: string, forceFull: boolean = false): Promise<{ 
    message: string; 
    task_id: string; 
    log_source_id: string;
  }> => {
    const response = await api.post(`/log-sources/${sourceId}/trigger-indexing`, null, {
      params: { force_full: forceFull }
    });
    return response.data;
  },

  getIndexingStatus: async (sourceId: string): Promise<{
    log_source_id: string;
    code_indexing_enabled: boolean;
    indexing_status: string;
    last_indexed_commit: string | null;
    last_indexed_at: string | null;
    indexing_error: string | null;
    token_status: string;
  }> => {
    const response = await api.get(`/log-sources/${sourceId}/indexing-status`);
    return response.data;
  },
};

// Code Indexing API
export const codeIndexingAPI = {
  // Trigger code indexing for a service
  trigger: async (serviceId: string, forceFull: boolean = false): Promise<{ message: string; service_id: string; task_id: string; force_full: boolean; trigger_reason: string }> => {
    const response = await api.post(`/code-indexing/services/${serviceId}/trigger`, null, {
      params: { force_full: forceFull }
    });
    return response.data;
  },

  // Get indexing status for a service
  getStatus: async (serviceId: string): Promise<{
    service_id: string;
    service_name: string;
    status: string;
    last_indexed_at: string | null;
    last_indexed_commit: string | null;
    indexing_trigger: string | null;
    indexing_error: string | null;
    git_repo_path: string | null;
    git_branch: string | null;
    code_indexing_enabled: boolean;
  }> => {
    const response = await api.get(`/code-indexing/services/${serviceId}/status`);
    return response.data;
  },

  // Get indexing history for a service
  getHistory: async (serviceId: string, limit: number = 10): Promise<{
    service_id: string;
    service_name: string;
    history: Array<{
      repository: string;
      last_indexed_commit: string | null;
      last_indexed_at: string | null;
      total_files_indexed: number;
      total_blocks_indexed: number;
      indexing_mode: string | null;
    }>;
    total_records: number;
  }> => {
    const response = await api.get(`/code-indexing/services/${serviceId}/history`, {
      params: { limit }
    });
    return response.data;
  },

  // Enable code indexing for a service
  enable: async (serviceId: string): Promise<{ message: string; service_id: string; code_indexing_enabled: boolean }> => {
    const response = await api.post(`/code-indexing/services/${serviceId}/enable`);
    return response.data;
  },

  // Disable code indexing for a service
  disable: async (serviceId: string): Promise<{ message: string; service_id: string; code_indexing_enabled: boolean }> => {
    const response = await api.post(`/code-indexing/services/${serviceId}/disable`);
    return response.data;
  },

  // Get indexing status for all services
  getAllStatus: async (): Promise<{
    services: Array<{
      service_id: string;
      service_name: string;
      status: string;
      last_indexed_at: string | null;
      last_indexed_commit: string | null;
      indexing_enabled: boolean;
      git_repo_path: string | null;
      git_branch: string | null;
    }>;
    total_services: number;
  }> => {
    const response = await api.get('/code-indexing/status/all');
    return response.data;
  },
};



export default api;
