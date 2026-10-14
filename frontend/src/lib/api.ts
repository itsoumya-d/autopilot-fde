// Mirrors backend SafetyStatus (models/schema.py). Keep in sync.
export type SafetyStatus = 'observation_only' | 'draft_only' | 'assisted' | 'autonomous';

export interface Channel {
  id: string;
  type: 'slack' | 'whatsapp' | 'email' | 'call';
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

// Mirrors backend AgentStatus (models/schema.py). Keep in sync.
export type AgentStatus = 'pending_approval' | 'deploying' | 'running' | 'paused' | 'stopped' | 'failed';

export interface Agent {
  id: string;
  process_id: string;
  name: string;
  status: AgentStatus;
  config: {
    traffic_percentage: number;
    enabled_steps: string[];
    approval_required: boolean;
    mode: 'draft' | 'assisted' | 'autonomous';
    confidence_threshold: number;
  };
  created_at: string;
  metrics: {
    [key: string]: unknown;
    drafts_created?: number | null;
    external_actions?: number | null;
    human_approval_rate?: number | null;
  };
}

export interface DashboardSummary {
  processes_discovered: number;
  average_opportunity_score: number;
  evidence_backed_hours: number;
  active_agents: number;
  pending_approvals: number;
}

// OCEL-shaped object log (v0.9 backend). Structural mirror of lib/objectLens.
export interface ObjectLogResponse {
  ocel_version: string;
  eventTypes: Array<{ name: string }>;
  events: Array<{
    id: string;
    type: string;
    time: string;
    attributes: Array<{ name: string; type: string; value: unknown }>;
    relationships: Array<{ objectId: string; qualifier: string }>;
  }>;
  objectTypes: Array<{ name: string }>;
  objects: Array<{
    id: string;
    type: string;
    relationships: Array<{ objectId: string; qualifier: string }>;
  }>;
  summaries: Record<string, { objects: number; events_touching: number }>;
}

const API_URL = (process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api').replace(/\/+$/, '');

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    cache: 'no-store',
  });
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    const detail = body && typeof body === 'object' && 'detail' in body ? body.detail : null;
    // FastAPI validation errors use an array; never render [object Object].
    const message = typeof detail === 'string' ? detail : Array.isArray(detail)
      ? detail.flatMap(item => item && typeof item === 'object' && typeof item.msg === 'string' ? [item.msg] : []).join('; ')
      : '';
    throw new Error(message || 'Request failed');
  }
  try {
    return await response.json() as T;
  } catch {
    throw new Error('The backend returned invalid JSON. Check the API URL and backend response.');
  }
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
  resumeAgent: (id: string) => request<Agent>(`/agents/${id}/resume`, { method: 'POST' }),
  removeAgent: (id: string) => request<{ message: string }>(`/agents/${id}`, { method: 'DELETE' }),
  objectLog: (limit = 500) =>
    request<ObjectLogResponse>(`/processes/object-log?limit=${limit}`),
};
