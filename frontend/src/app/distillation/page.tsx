'use client';

import React, { useEffect, useRef, useState } from 'react';
import { Cpu, DollarSign, ShieldCheck, Play, CheckCircle2, AlertCircle, FileCode, Sparkles } from 'lucide-react';
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
    <div className="space-y-8 max-w-6xl">
      <div>
        <h1 className="text-3xl font-bold text-white tracking-tight flex items-center gap-3">
          <span className="p-2 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-xl text-white shadow-lg shadow-purple-500/20"><Cpu size={24} aria-hidden="true" /></span>
          Model Distillation Studio
        </h1>
        <p className="text-slate-400 mt-2 text-sm max-w-3xl">Generate a dataset and local training recipes through your configured backend. This workflow does not call a teacher model, train a model, or deploy a service.</p>
        <p className="text-cyan-300 mt-2 text-xs">Backend mode · No automatic demo fallback. Generated files stay on the backend filesystem.</p>
      </div>

      <section aria-labelledby="cost-heading" className="bg-gradient-to-r from-emerald-950/40 via-slate-900 to-slate-900 border border-emerald-500/30 rounded-2xl p-6 space-y-3">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-1">
            <div className="flex items-center gap-2 text-emerald-400 text-xs font-bold uppercase tracking-wider"><DollarSign size={16} aria-hidden="true" /> Illustrative Cost Estimate</div>
            <h2 id="cost-heading" className="text-2xl font-extrabold text-white">${Math.abs(netSavings).toLocaleString()} / year {netSavings >= 0 ? 'potential savings' : 'additional cost'}</h2>
            <p className="text-slate-400 text-xs">Assumed cloud API: ${annualTeacherCost.toLocaleString()}/yr · Assumed local inference: ${annualStudentCost.toLocaleString()}/yr.</p>
          </div>
          <div className="flex items-center gap-4">
            <label htmlFor="monthly-volume" className="text-xs text-slate-400 whitespace-nowrap">Monthly volume</label>
            <input id="monthly-volume" type="range" min="10000" max="500000" step="10000" value={monthlyVolume} onChange={(e) => setMonthlyVolume(Number(e.target.value))} className="accent-emerald-500 w-40" />
            <output htmlFor="monthly-volume" className="text-xs font-mono font-bold text-emerald-300 w-20 text-right">{monthlyVolume.toLocaleString()}</output>
          </div>
        </div>
        <p className="text-xs text-slate-400">Assumptions: 1,500 tokens per operation, $5 per million tokens blended, and $120/month local inference. These are illustrative inputs, not live model prices. Excludes training, evaluation, engineering, and operations costs; equivalent model quality is not established.</p>
      </section>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <section aria-labelledby="model-heading" className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-5">
          <h2 id="model-heading" className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2"><Sparkles size={16} className="text-purple-400" aria-hidden="true" />1. Configure Recipe</h2>
          <fieldset disabled={isGenerating} className="space-y-3 disabled:opacity-70">
            <div>
              <label htmlFor="teacher-model" className="text-xs font-semibold text-slate-400 block mb-1.5">Teacher model reference (metadata only)</label>
              <select id="teacher-model" value={teacher} onChange={(e) => { setTeacher(e.target.value as TeacherModel); clearJobResult(); }} className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-sm text-white focus:outline-none focus:border-purple-500">
                <option value="gpt-4o">OpenAI GPT-4o</option>
                <option value="claude-3-5-sonnet">Anthropic Claude 3.5 Sonnet</option>
                <option value="deepseek-r1">DeepSeek-R1</option>
                <option value="meta-llama/Meta-Llama-3.1-405B-Instruct">Meta Llama 3.1 405B Instruct</option>
              </select>
            </div>
            <div>
              <label htmlFor="student-model" className="text-xs font-semibold text-slate-400 block mb-1.5">Target student model</label>
              <select id="student-model" value={student} onChange={(e) => { setStudent(e.target.value as StudentModel); clearJobResult(); }} className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-sm text-white focus:outline-none focus:border-purple-500">
                <option value="Qwen/Qwen2.5-7B-Instruct">Qwen 2.5 7B Instruct</option>
                <option value="meta-llama/Meta-Llama-3.1-8B-Instruct">Meta Llama 3.1 8B Instruct</option>
                <option value="mistralai/Mistral-7B-Instruct-v0.3">Mistral 7B Instruct v0.3</option>
                <option value="google/gemma-2-9b-it">Google Gemma 2 9B Instruct</option>
              </select>
            </div>
            <div className="bg-slate-950/80 border border-purple-500/30 rounded-xl p-4 space-y-3">
              <div className="flex items-center gap-2 text-xs font-bold text-purple-300 uppercase tracking-wider"><ShieldCheck size={16} aria-hidden="true" />Usage Attestations</div>
              <div className="space-y-2 text-xs text-slate-300">
                <label className="flex items-start gap-2 cursor-pointer"><input type="checkbox" checked={attestInternal} onChange={(e) => { setAttestInternal(e.target.checked); clearJobResult(); }} className="accent-purple-500 mt-0.5 rounded" /><span>I intend to use these artifacts for internal enterprise workflow automation.</span></label>
                <label className="flex items-start gap-2 cursor-pointer"><input type="checkbox" checked={attestWaiver} onChange={(e) => { setAttestWaiver(e.target.checked); clearJobResult(); }} className="accent-purple-500 mt-0.5 rounded" /><span>I will not use these artifacts to develop or sell a competing general-purpose foundation model service.</span></label>
              </div>
              <p className="text-xs text-slate-400">These declarations do not grant a license or establish compliance. Review data rights, model/provider terms, and applicable obligations before using or training on the generated dataset.</p>
            </div>
            <label className="flex items-start gap-2 text-xs text-slate-300 cursor-pointer"><input type="checkbox" checked={allowSynthetic} onChange={(e) => { setAllowSynthetic(e.target.checked); clearJobResult(); }} className="accent-purple-500 mt-0.5" /><span>Allow synthetic demo samples if no workspace evidence is available. Demo data is for testing the recipe workflow only.</span></label>
          </fieldset>
        </section>

        <section aria-labelledby="preview-heading" className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-4">
          <h2 id="preview-heading" className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2"><ShieldCheck size={16} className="text-cyan-400" aria-hidden="true" />2. Pattern-Based Redaction Preview</h2>
          <p id="preview-help" className="text-xs text-slate-400">Regex patterns can miss names and other personal or sensitive data. Review outputs manually. This preview is separate from the workspace dataset and does not certify anonymization or legal compliance.</p>
          <div className="space-y-2">
            <label htmlFor="preview-text" className="text-xs font-semibold text-slate-400">Sample operational text</label>
            <textarea id="preview-text" aria-describedby="preview-help" value={previewText} onChange={(e) => updatePreviewText(e.target.value)} rows={3} className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs text-white focus:outline-none focus:border-cyan-500 font-mono" />
            <button onClick={handlePreviewScrub} disabled={isPreviewing || !previewText.trim()} className="px-3 py-1.5 bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 border border-cyan-500/40 rounded text-xs font-semibold disabled:opacity-50 disabled:cursor-not-allowed">{isPreviewing ? 'Checking redactions…' : 'Test PII Sanitizer'}</button>
          </div>
          <div aria-live="polite" aria-busy={isPreviewing}>
            {previewError && <p role="alert" className="text-sm text-rose-300 flex items-start gap-2"><AlertCircle size={16} className="shrink-0" aria-hidden="true" />{previewError}</p>}
            {scrubbedResult && <div className="bg-slate-950 border border-slate-800 rounded-lg p-3 text-xs space-y-1"><div className="text-slate-400">Backend preview ({scrubbedResult.redactions_count} pattern matches redacted):</div><p className="text-slate-200 font-mono text-[11px] whitespace-pre-wrap break-words">{scrubbedResult.scrubbed || '(Empty output)'}</p></div>}
          </div>
          <div className="pt-2 space-y-2">
            <button onClick={handleExecuteDistill} disabled={isGenerating || !attestInternal || !attestWaiver} aria-describedby="generation-help" className={`w-full py-3 rounded-xl font-bold text-sm flex items-center justify-center gap-2 transition-all ${isGenerating || !attestInternal || !attestWaiver ? 'bg-slate-800 text-slate-500 cursor-not-allowed' : 'bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-slate-950 shadow-lg shadow-cyan-500/20'}`}>{isGenerating ? 'Generating dataset and recipes…' : <><Play size={16} aria-hidden="true" />Compile Dataset & Generate Training Recipes</>}</button>
            <p id="generation-help" className="text-xs text-slate-400">Confirm both usage declarations to generate files from workspace process evidence. Review provenance and labels before training; workspace records may include seeded demo data.</p>
            {isGenerating && <p role="status" className="text-xs text-cyan-300">Waiting for the backend to finish file generation. Leaving this page does not cancel backend work.</p>}
            {jobError && <p role="alert" className="text-sm text-rose-300">{jobError} A lost response may leave a job on the backend; check its job list before retrying.</p>}
          </div>
        </section>
      </div>

      {jobResult && <section aria-label="Generation result" aria-live="polite" className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-4">
        <div className={`flex items-center gap-2 font-bold text-sm ${jobResult.status === 'completed' ? 'text-emerald-400' : 'text-cyan-300'}`}>
          {jobResult.status === 'completed' && <CheckCircle2 size={18} aria-hidden="true" />}
          {jobResult.status === 'completed' ? 'Dataset and recipes generated' : `Backend generation status: ${jobResult.status.replaceAll('_', ' ')}`}: {jobResult.id}
        </div>
        {jobResult.status === 'completed' ? <>
          <p className={`text-sm font-semibold ${jobResult.used_synthetic_samples ? 'text-amber-300' : 'text-cyan-300'}`}>{jobResult.used_synthetic_samples ? 'Synthetic demo dataset: these samples are fabricated for testing.' : 'Source: workspace process evidence (which may include seeded demo records).'}</p>
          <p className="text-xs text-slate-400">The backend reported {jobResult.sample_count} dataset rows and {jobResult.pii_scrubbed_count} pattern-based redactions. No model was trained or deployed. Inspect these backend-local files and validate the data, licenses, recipe, and model quality before running them.</p>
          <p className="text-xs text-slate-400 break-all">Backend output directory: {jobResult.output_dir}</p>
          <ul className="grid grid-cols-1 md:grid-cols-2 gap-3">{jobResult.generated_recipe_files.map((file) => <li key={file} className="bg-slate-950 border border-slate-800 rounded-lg p-3 flex items-start gap-2 text-xs text-slate-300 font-mono"><FileCode size={16} className="text-cyan-400 shrink-0" aria-hidden="true" /><span className="break-all">{file}</span></li>)}</ul>
        </> : <p className="text-xs text-slate-400">The backend has not confirmed completed files. Check the backend job record for progress.</p>}
      </section>}
    </div>
  );
}
