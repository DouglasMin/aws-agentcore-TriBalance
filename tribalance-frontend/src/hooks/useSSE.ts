import { useCallback, useRef } from 'react';
import type { AgentEvent } from '../store/events';
import { useRunStore } from '../store/runStore';

const PROXY_URL = import.meta.env.VITE_PROXY_URL || '';

interface InvokePayload {
  s3_key: string;
  week_start?: string;
}

/**
 * Consume a Lambda Function URL SSE response and dispatch events into the
 * run store. Uses fetch + ReadableStream (EventSource is GET-only, we need
 * to POST the payload).
 */
export function useInvoke() {
  const dispatch = useRunStore((s) => s.dispatch);
  const reset = useRunStore((s) => s.reset);
  const setConnecting = useRunStore((s) => s.setConnecting);
  const abortRef = useRef<AbortController | null>(null);

  const invoke = useCallback(
    async (payload: InvokePayload) => {
      // Cancel any previous stream
      if (abortRef.current) abortRef.current.abort();
      const ctrl = new AbortController();
      abortRef.current = ctrl;

      reset();

      // Immediate visual feedback — don't wait for the server
      setConnecting();

      if (!PROXY_URL) {
        dispatch({
          event: 'error',
          message: 'VITE_PROXY_URL is not configured.',
        });
        return;
      }

      let response: Response;
      try {
        response = await fetch(`${PROXY_URL}/invoke`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
          signal: ctrl.signal,
        });
      } catch (err) {
        if (ctrl.signal.aborted) return;
        dispatch({
          event: 'error',
          message: `network: ${String(err)}`,
        });
        return;
      }

      if (!response.ok || !response.body) {
        dispatch({
          event: 'error',
          message: `proxy returned ${response.status}`,
        });
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        let chunk: ReadableStreamReadResult<Uint8Array>;
        try {
          chunk = await reader.read();
        } catch (err) {
          if (ctrl.signal.aborted) return;
          dispatch({
            event: 'error',
            message: `stream read failed: ${String(err)}`,
          });
          return;
        }
        if (chunk.done) break;
        buffer += decoder.decode(chunk.value, { stream: true });

        // SSE frames are separated by \n\n. A frame is one or more lines;
        // the data: line carries our JSON.
        let sepIdx;
        while ((sepIdx = buffer.indexOf('\n\n')) !== -1) {
          const frame = buffer.slice(0, sepIdx);
          buffer = buffer.slice(sepIdx + 2);
          const parsed = parseFrame(frame);
          if (parsed) dispatch(parsed);
        }
      }
    },
    [dispatch, reset, setConnecting],
  );

  const abort = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  return { invoke, abort };
}

function parseFrame(frame: string): AgentEvent | null {
  // Each frame can have multiple lines. We only care about `data:`.
  const lines = frame.split('\n');
  const dataLines = lines
    .filter((ln) => ln.startsWith('data:'))
    .map((ln) => ln.slice(5).trimStart());
  if (dataLines.length === 0) return null;
  const json = dataLines.join('\n');
  try {
    return JSON.parse(json) as AgentEvent;
  } catch {
    return null;
  }
}
