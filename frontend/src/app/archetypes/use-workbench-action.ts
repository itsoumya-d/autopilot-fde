'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

/** One in-flight action per panel. Canceled/older views never receive results. */
export function useWorkbenchAction<T>() {
  const [result, setResult] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const active = useRef<AbortController | null>(null);

  const reset = useCallback(() => {
    active.current?.abort();
    active.current = null;
    setResult(null);
    setError(null);
    setPending(false);
  }, []);

  useEffect(() => () => {
    active.current?.abort();
    active.current = null;
  }, []);

  const run = useCallback(async (task: (signal: AbortSignal) => Promise<T>, preserveResult = false) => {
    if (active.current) return;
    const controller = new AbortController();
    active.current = controller;
    setPending(true);
    setError(null);
    if (!preserveResult) setResult(null);
    try {
      const value = await task(controller.signal);
      if (active.current === controller) setResult(value);
    } catch (error: unknown) {
      if (active.current === controller && !controller.signal.aborted) {
        setError(error instanceof Error ? error.message : 'The request failed. No result was confirmed.');
      }
    } finally {
      if (active.current === controller) {
        active.current = null;
        setPending(false);
      }
    }
  }, []);

  return { result, error, pending, run, reset };
}
