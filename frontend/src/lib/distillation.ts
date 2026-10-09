import { request } from './api';

export type TeacherModel = 'gpt-4o' | 'claude-3-5-sonnet' | 'deepseek-r1' | 'meta-llama/Meta-Llama-3.1-405B-Instruct';
export type StudentModel = 'Qwen/Qwen2.5-7B-Instruct' | 'meta-llama/Meta-Llama-3.1-8B-Instruct' | 'mistralai/Mistral-7B-Instruct-v0.3' | 'google/gemma-2-9b-it';

export interface ScrubPreview {
  original: string;
  scrubbed: string;
  redactions_count: number;
}

export interface CreateDistillationJob {
  teacher_model: TeacherModel;
  student_model: StudentModel;
  attest_internal_use_only: boolean;
  commercial_foundation_competition_waiver: boolean;
  allow_synthetic_samples: boolean;
}

export interface DistillationJob {
  id: string;
  teacher_model: TeacherModel;
  student_model: StudentModel;
  status: 'pending' | 'extracting' | 'scrubbing_pii' | 'generating_recipe' | 'completed' | 'failed';
  sample_count: number;
  pii_scrubbed_count: number;
  output_dir: string;
  generated_recipe_files: string[];
  used_synthetic_samples: boolean;
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);
const isCount = (value: unknown): value is number =>
  typeof value === 'number' && Number.isSafeInteger(value) && value >= 0;
const isText = (value: unknown): value is string => typeof value === 'string' && value.trim().length > 0;
const statuses = ['pending', 'extracting', 'scrubbing_pii', 'generating_recipe', 'completed', 'failed'];

/** A 2xx error object or partial JSON is not a successful result. */
export const distillationApi = {
  async scrubPreview(text: string, signal?: AbortSignal): Promise<ScrubPreview> {
    const value = await request<unknown>('/distillation/scrub-preview', {
      method: 'POST', body: JSON.stringify({ text }), signal,
    });
    if (!isRecord(value) || value.original !== text || typeof value.scrubbed !== 'string' || !isCount(value.redactions_count)) {
      throw new Error('The backend returned an invalid sanitizer result. No preview was accepted.');
    }
    return value as unknown as ScrubPreview;
  },

  async createJob(payload: CreateDistillationJob, signal?: AbortSignal): Promise<DistillationJob> {
    const value = await request<unknown>('/distillation/jobs', {
      method: 'POST', body: JSON.stringify(payload), signal,
    });
    if (!isRecord(value) || !isText(value.id) ||
      value.teacher_model !== payload.teacher_model || value.student_model !== payload.student_model ||
      typeof value.status !== 'string' || !statuses.includes(value.status) ||
      !isCount(value.sample_count) || !isCount(value.pii_scrubbed_count) || !isText(value.output_dir) ||
      !Array.isArray(value.generated_recipe_files) || !value.generated_recipe_files.every(isText) ||
      typeof value.used_synthetic_samples !== 'boolean' ||
      (value.used_synthetic_samples && !payload.allow_synthetic_samples) ||
      (value.status === 'completed' && (value.generated_recipe_files.length === 0 || value.sample_count === 0))) {
      throw new Error('The backend returned an invalid generation result. Completion could not be verified.');
    }
    return value as unknown as DistillationJob;
  },
};
