'use client';

import React, { useEffect, useRef, useState } from 'react';
import { FileCode, Play } from 'lucide-react';
import { EmptyState, ErrorState, PageHeader, SectionHeader, SourceLabel, StatusBadge } from '@/components/Workspace';
import { distillationApi, type DistillationJob, type ScrubPreview, type StudentModel, type TeacherModel } from '@/lib/distillation';

const errorMessage = (error: unknown) => error instanceof Error ? error.message : 'The request failed. Check the backend connection and try again.';

export default function DistillationPage() {
  const [teacher, setTeacher] = useState<TeacherModel>('gpt-4o');
  const [student, setStudent] = useState<StudentModel>('Qwen/Qwen2.5-7B-Instruct');
  const [attestInternal, setAttestInternal] = useState(false);
  const [attestWaiver, setAttestWaiver] = useState(false);
  const [allowSynthetic, setAllowSynthetic] = useState(false);
  const [monthlyVolume, setMonthlyVolume] = useState(50000);
  const [previewText, setPreviewText] = useState('Contact Alice at alice@example.com or 555-019-2834 regarding invoice #9901.');
  const [scrubbedResult, setScrubbedResult] = useState<ScrubPreview | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [jobResult, setJobResult] = useState<DistillationJob | null>(null);
  const [jobError, setJobError] = useState<string | null>(null);
  const previewRequest = useRef<{ id: number; controller: AbortController | null }>({ id: 0, controller: null });
  const jobRequest = useRef<{ id: number; controller: AbortController | null }>({ id: 0, controller: null });

  useEffect(() => () => {
    // Ignore responses from a previous page instance even when fetch ignores abort.
    previewRequest.current.id += 1;
    previewRequest.current.controller?.abort();
    jobRequest.current.id += 1;
    jobRequest.current.controller?.abort();
  }, []);

  const annualTeacherCost = monthlyVolume * 1500 / 1_000_000 * 5 * 12;
  const annualStudentCost = 120 * 12;
  const netSavings = annualTeacherCost - annualStudentCost;

  const updatePreviewText = (text: string) => {
    previewRequest.current.id += 1;
    previewRequest.current.controller?.abort();
    previewRequest.current.controller = null;
    setIsPreviewing(false);
    setPreviewText(text);
    setScrubbedResult(null);
    setPreviewError(null);
  };

  const clearJobResult = () => {
    setJobResult(null);
    setJobError(null);
  };

  const handlePreviewScrub = async () => {
    // Ref is a synchronous lock; state alone allows repeat clicks before rerender.
    if (previewRequest.current.controller || !previewText.trim()) return;
    const controller = new AbortController();
    const id = ++previewRequest.current.id;
    previewRequest.current.controller = controller;
    setIsPreviewing(true);
    setPreviewError(null);
    setScrubbedResult(null);
    try {
      const result = await distillationApi.scrubPreview(previewText, controller.signal);
      if (id === previewRequest.current.id) setScrubbedResult(result);
    } catch (error) {
      if (id === previewRequest.current.id) setPreviewError(errorMessage(error));
    } finally {
      if (id === previewRequest.current.id) {
        previewRequest.current.controller = null;
        setIsPreviewing(false);
      }
    }
  };

  const handleExecuteDistill = async () => {
    if (jobRequest.current.controller || !attestInternal || !attestWaiver) return;
    const controller = new AbortController();
    const id = ++jobRequest.current.id;
    jobRequest.current.controller = controller;
    setIsGenerating(true);
    setJobError(null);
    setJobResult(null);
    try {
      const result = await distillationApi.createJob({
        teacher_model: teacher,
        student_model: student,
        attest_internal_use_only: attestInternal,
        commercial_foundation_competition_waiver: attestWaiver,
        allow_synthetic_samples: allowSynthetic,
      }, controller.signal);
      if (id !== jobRequest.current.id) return;
      if (result.status === 'failed') {
        setJobError(`Recipe generation failed for ${result.id}. No completed artifacts were confirmed.`);
      } else {
        setJobResult(result);
      }
    } catch (error) {
      if (id === jobRequest.current.id) setJobError(errorMessage(error));
    } finally {
      if (id === jobRequest.current.id) {
        jobRequest.current.controller = null;
        setIsGenerating(false);
      }
    }
  };

  return (
    <div className="page-stack">
      <PageHeader eyebrow="Studio / Model Recipes" title="Model Recipes" description="Generate a dataset and local training recipes through your configured backend. This workflow does not call a teacher model, train a model, or deploy a service." />
      <SourceLabel>Backend mode · No automatic demo fallback. Generated files stay on the backend filesystem.</SourceLabel>

      <div className="workspace-grid">
        <section aria-labelledby="model-heading" className="surface surface-pad space-y-5">
          <div><p className="page-kicker">01 / Configuration</p><h2 id="model-heading" className="mt-2 text-lg font-semibold">Configure recipe</h2></div>
          <fieldset disabled={isGenerating} className="min-w-0 space-y-5 disabled:opacity-70">
            <div>
              <label htmlFor="teacher-model" className="label">Teacher model reference (metadata only)</label>
              <select id="teacher-model" value={teacher} onChange={(e) => { setTeacher(e.target.value as TeacherModel); clearJobResult(); }} className="field">
                <option value="gpt-4o">OpenAI GPT-4o</option>
                <option value="claude-3-5-sonnet">Anthropic Claude 3.5 Sonnet</option>
                <option value="deepseek-r1">DeepSeek-R1</option>
                <option value="meta-llama/Meta-Llama-3.1-405B-Instruct">Meta Llama 3.1 405B Instruct</option>
              </select>
            </div>
            <div>
              <label htmlFor="student-model" className="label">Target student model</label>
              <select id="student-model" value={student} onChange={(e) => { setStudent(e.target.value as StudentModel); clearJobResult(); }} className="field">
                <option value="Qwen/Qwen2.5-7B-Instruct">Qwen 2.5 7B Instruct</option>
                <option value="meta-llama/Meta-Llama-3.1-8B-Instruct">Meta Llama 3.1 8B Instruct</option>
                <option value="mistralai/Mistral-7B-Instruct-v0.3">Mistral 7B Instruct v0.3</option>
                <option value="google/gemma-2-9b-it">Google Gemma 2 9B Instruct</option>
              </select>
            </div>
            <div className="border-t border-[var(--border)] pt-5 space-y-3">
              <h3 className="font-semibold">Usage attestations</h3>
              <label className="flex cursor-pointer items-start gap-3 text-sm"><input type="checkbox" checked={attestInternal} onChange={(e) => { setAttestInternal(e.target.checked); clearJobResult(); }} className="mt-1 accent-[var(--accent)]" /><span>I intend to use these artifacts for internal enterprise workflow automation.</span></label>
              <label className="flex cursor-pointer items-start gap-3 text-sm"><input type="checkbox" checked={attestWaiver} onChange={(e) => { setAttestWaiver(e.target.checked); clearJobResult(); }} className="mt-1 accent-[var(--accent)]" /><span>I will not use these artifacts to develop or sell a competing general-purpose foundation model service.</span></label>
              <p className="metadata">These declarations do not grant a license or establish compliance. Review data rights, model/provider terms, and applicable obligations before using or training on the generated dataset.</p>
            </div>
            <label className="flex cursor-pointer items-start gap-3 border-t border-[var(--border)] pt-5 text-sm"><input type="checkbox" checked={allowSynthetic} onChange={(e) => { setAllowSynthetic(e.target.checked); clearJobResult(); }} className="mt-1 accent-[var(--accent)]" /><span>Allow synthetic demo samples if no workspace evidence is available. Demo data is for testing the recipe workflow only.</span></label>
          </fieldset>
        </section>

        <aside className="inspector space-y-5" aria-label="Generation controls">
          <div><p className="page-kicker">02 / Generate local files</p><h2 className="mt-2 text-lg font-semibold">Review before compiling</h2></div>
          <dl className="space-y-4 text-sm">
            <div className="flex flex-wrap justify-between gap-2 border-b border-[var(--border)] pb-3"><dt className="muted">Teacher reference</dt><dd className="mono break-all">{teacher}</dd></div>
            <div className="space-y-2 border-b border-[var(--border)] pb-3"><dt className="muted">Student model</dt><dd className="mono break-all">{student}</dd></div>
            <div className="flex flex-wrap justify-between gap-2"><dt className="muted">Synthetic sample fallback</dt><dd>{allowSynthetic ? 'Explicitly allowed' : 'Not allowed'}</dd></div>
          </dl>
          <p id="generation-help" className="muted text-sm">Confirm both usage declarations to generate files from workspace process evidence. Review provenance and labels before training; workspace records may include seeded demo data.</p>
          <button onClick={handleExecuteDistill} disabled={isGenerating || !attestInternal || !attestWaiver} aria-describedby="generation-help" className="button-primary w-full">{isGenerating ? 'Generating dataset and recipes…' : <><Play size={16} className="shrink-0" aria-hidden="true" /><span>Compile Dataset &amp; Generate Training Recipes</span></>}</button>
          {isGenerating && <p role="status" className="muted text-sm">Waiting for the backend to finish file generation. Leaving this page does not cancel backend work.</p>}
          {jobError && <ErrorState>{jobError} A lost response may leave a job on the backend; check its job list before retrying.</ErrorState>}
          <p className="metadata">This produces recipe files only. Model training, deployment, and quality evaluation are separate steps.</p>
        </aside>
      </div>

      {jobResult && <section aria-label="Generation result" aria-live="polite" className="surface surface-pad space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <h2 className="break-words text-lg font-semibold">{jobResult.status === 'completed' ? 'Dataset and recipes generated' : `Backend generation status: ${jobResult.status.replaceAll('_', ' ')}`}: {jobResult.id}</h2>
          <StatusBadge tone={jobResult.status === 'completed' ? 'success' : 'warning'}>{jobResult.status.replaceAll('_', ' ')}</StatusBadge>
        </div>
        {jobResult.status === 'completed' ? <>
          <p className="text-sm font-medium">{jobResult.used_synthetic_samples ? 'Synthetic demo dataset: these samples are fabricated for testing.' : 'Source: workspace process evidence (which may include seeded demo records).'}</p>
          <p className="muted text-sm">The backend reported {jobResult.sample_count} dataset rows and {jobResult.pii_scrubbed_count} pattern-based redactions. No model was trained or deployed. Inspect these backend-local files and validate the data, licenses, recipe, and model quality before running them.</p>
          <p className="metadata break-all">Backend output directory: {jobResult.output_dir}</p>
          <ul className="divide-y divide-[var(--border)] border-y border-[var(--border)]">{jobResult.generated_recipe_files.map((file) => <li key={file} className="flex items-start gap-3 py-3 text-sm"><FileCode size={16} className="mt-0.5 shrink-0 text-[var(--text-muted)]" aria-hidden="true" /><span className="mono break-all">{file}</span></li>)}</ul>
        </> : <p className="muted text-sm">The backend has not confirmed completed files. Check the backend job record for progress.</p>}
      </section>}

      <section aria-labelledby="preview-heading" className="surface surface-pad space-y-5">
        <div><p className="page-kicker">Review tool / separate from generation</p><h2 id="preview-heading" className="mt-2 text-lg font-semibold">Pattern-based redaction preview</h2></div>
        <p id="preview-help" className="muted max-w-3xl text-sm">Regex patterns can miss names and other personal or sensitive data. Review outputs manually. This preview is separate from the workspace dataset and does not certify anonymization or legal compliance.</p>
        <div className="grid gap-5 lg:grid-cols-2">
          <div className="space-y-3">
            <label htmlFor="preview-text" className="label">Sample operational text</label>
            <textarea id="preview-text" aria-describedby="preview-help" value={previewText} onChange={(e) => updatePreviewText(e.target.value)} rows={5} className="field mono resize-y" />
            <button onClick={handlePreviewScrub} disabled={isPreviewing || !previewText.trim()} className="button-secondary">{isPreviewing ? 'Checking redactions…' : 'Test PII Sanitizer'}</button>
          </div>
          <div aria-live="polite" aria-busy={isPreviewing} className="min-w-0">
            <p className="label">Redaction output</p>
            {previewError && <ErrorState>{previewError}</ErrorState>}
            {scrubbedResult ? <div className="rounded-md border border-[var(--border)] bg-[var(--surface-subtle)] p-4"><div className="metadata mb-3">Backend preview ({scrubbedResult.redactions_count} pattern matches redacted):</div><p className="mono whitespace-pre-wrap break-words text-sm">{scrubbedResult.scrubbed || '(Empty output)'}</p></div> : !previewError && <EmptyState title={isPreviewing ? 'Checking the entered text…' : 'No preview yet'}>Run the pattern check to compare the returned text here.</EmptyState>}
          </div>
        </div>
      </section>

      <section aria-labelledby="cost-heading" className="border-t border-[var(--border)] pt-6 space-y-4">
        <SectionHeader title="Illustrative estimate" description="A worksheet with fixed assumptions, separate from recipe generation." actions={<SourceLabel>Static coefficients</SourceLabel>} />
        <div className="grid gap-6 md:grid-cols-2 md:items-center">
          <div><h3 id="cost-heading" className="text-2xl font-semibold tabular-nums">${Math.abs(netSavings).toLocaleString()} / year {netSavings >= 0 ? 'potential savings' : 'additional cost'}</h3><p className="muted mt-2 text-sm">Assumed cloud API: ${annualTeacherCost.toLocaleString()}/yr · Assumed local inference: ${annualStudentCost.toLocaleString()}/yr.</p></div>
          <div className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-3"><label htmlFor="monthly-volume" className="label col-span-2">Monthly volume</label><input id="monthly-volume" type="range" min="10000" max="500000" step="10000" value={monthlyVolume} onChange={(e) => setMonthlyVolume(Number(e.target.value))} className="min-w-0 w-full accent-[var(--accent)]" /><output htmlFor="monthly-volume" className="mono text-sm">{monthlyVolume.toLocaleString()}</output></div>
        </div>
        <p className="metadata max-w-4xl">Assumptions: 1,500 tokens per operation, $5 per million tokens blended, and $120/month local inference. These are illustrative inputs, not live model prices. Excludes training, evaluation, engineering, and operations costs; equivalent model quality is not established.</p>
      </section>
    </div>
  );
}
