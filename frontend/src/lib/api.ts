export type SafetyStatus = 'review_required' | 'draft_only' | 'blocked';

export interface Channel {
  id: string;
  type: 'slack';
  name: string;
  status: 'active' | 'inactive' | 'error';
  message_count: number;
  read_only: boolean;
}

export interface Activity {
  id: string;
  case_id: string;
  name: string;
  category: string;
  actors: string[];
  timestamp: string;
  source_messages: string[];
  evidence: string;
  confidence: number;
}

export interface ProcessEdge {
  source: string;
  target: string;
  frequency: number;
  probability: number;
  avg_duration_minutes: number;
}

export interface Process {
  id: string;
  name: string;
  description: string;
  activities: Activity[];
  edges: ProcessEdge[];
  metrics: {
    volume_per_month: number;
    avg_completion_minutes: number;
    trace_count: number;
    pattern_consistency: number;
    evidence_count: number;
  };
  evidence_case_ids: string[];
  safety_notes: string[];
}

export interface APScore {
  process_id: string;
  score: number;
  value_score: number;
  feasibility_score: number;
  evidence_confidence: number;
  factors: Record<string, number>;
  recommendation: string;
  recommended_mode: SafetyStatus;
  eligible_steps: string[];
  blocked_steps: string[];
  estimated_hours_saved_monthly: number;
}

export interface Agent {
  id: string;
  process_id: string;
  name: string;
  status: 'pending_approval' | 'running' | 'paused';
  config: {
    traffic_percentage: number;
    enabled_steps: string[];
    approval_required: boolean;
    mode: 'draft';
    confidence_threshold: number;
  };
  created_at: string;
  metrics: Record<string, number | null>;
}

export interface DashboardSummary {
  processes_discovered: number;
  average_opportunity_score: number;
  evidence_backed_hours: number;
  active_agents: number;
  pending_approvals: number;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    cache: 'no-store',
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(body.detail || 'Request failed');
  }
  return response.json() as Promise<T>;
}

export const api = {
  dashboard: () => request<DashboardSummary>('/dashboard/'),
  channels: () => request<Channel[]>('/channels/'),
  processes: () => request<Process[]>('/processes/'),
  discover: () => request<{ message: string; processes: number; activities: number }>('/processes/discover', { method: 'POST' }),
  scores: () => request<APScore[]>('/scores/'),
  recommendations: () => request('/scores/recommendations') as Promise<Array<{ process_id: string; process_name: string; priority: number; wave: string; estimated_hours_saved: number; risk_level: string; missing_capabilities: string[] }>>,
  agents: () => request<Agent[]>('/agents/'),
  deploy: (payload: { process_id: string; name: string; config: Agent['config'] }) => request<Agent>('/agents/deploy', { method: 'POST', body: JSON.stringify(payload) }),
  approveAgent: (id: string) => request<Agent>(`/agents/${id}/approve`, { method: 'POST' }),
  pauseAgent: (id: string) => request<Agent>(`/agents/${id}/pause`, { method: 'POST' }),
  removeAgent: (id: string) => request<{ message: string }>(`/agents/${id}`, { method: 'DELETE' }),
};
