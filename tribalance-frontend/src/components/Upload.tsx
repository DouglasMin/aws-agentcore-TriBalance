import { useRef, useState } from 'react';
import { useInvoke } from '../hooks/useSSE';
import { useRunStore } from '../store/runStore';

const PROXY_URL = import.meta.env.VITE_PROXY_URL || '';
const SAMPLE_S3_KEY = 'samples/export_sample.xml';

interface PresignResponse {
  url: string;
  key: string;
  expires_in: number;
}

type UploadState =
  | { kind: 'idle' }
  | { kind: 'uploading'; name: string }
  | { kind: 'uploaded'; name: string; s3Key: string }
  | { kind: 'error'; message: string };

export function Upload() {
  const { invoke, abort } = useInvoke();
  const reset = useRunStore((s) => s.reset);
  const status = useRunStore((s) => s.status);
  const fileRef = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const [upload, setUpload] = useState<UploadState>({ kind: 'idle' });

  async function handleFile(f: File) {
    setUpload({ kind: 'uploading', name: f.name });

    if (!PROXY_URL) {
      setUpload({ kind: 'error', message: 'VITE_PROXY_URL not set' });
      return;
    }

    let pre: PresignResponse;
    try {
      const resp = await fetch(`${PROXY_URL}/upload-url`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          filename: f.name.replace(/[^A-Za-z0-9._-]/g, '_'),
          content_type: f.type || 'application/xml',
        }),
      });
      if (!resp.ok) throw new Error(`presign: HTTP ${resp.status}`);
      pre = (await resp.json()) as PresignResponse;
    } catch (err: unknown) {
      setUpload({ kind: 'error', message: `presign failed: ${errMsg(err)}` });
      return;
    }

    try {
      const putResp = await fetch(pre.url, {
        method: 'PUT',
        headers: { 'Content-Type': f.type || 'application/xml' },
        body: f,
      });
      if (!putResp.ok) throw new Error(`PUT: HTTP ${putResp.status}`);
    } catch (err: unknown) {
      setUpload({ kind: 'error', message: `upload failed: ${errMsg(err)}` });
      return;
    }

    setUpload({ kind: 'uploaded', name: f.name, s3Key: pre.key });

    await invoke({
      s3_key: pre.key,
      week_start: new Date().toISOString().slice(0, 10),
    });
  }

  function onInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (f) void handleFile(f);
  }

  function onDrop(e: React.DragEvent<HTMLLabelElement>) {
    e.preventDefault();
    setDrag(false);
    const f = e.dataTransfer.files?.[0];
    if (f) void handleFile(f);
  }

  function runCurrent() {
    if (upload.kind === 'uploaded') {
      reset();
      void invoke({
        s3_key: upload.s3Key,
        week_start: new Date().toISOString().slice(0, 10),
      });
    }
  }

  function runSample() {
    reset();
    setUpload({ kind: 'uploaded', name: 'export_sample.xml', s3Key: SAMPLE_S3_KEY });
    void invoke({
      s3_key: SAMPLE_S3_KEY,
      week_start: new Date().toISOString().slice(0, 10),
    });
  }

  const busy = status === 'live' || upload.kind === 'uploading';
  const labelText = zoneLabel(upload);
  const labelClass = zoneClass(upload, drag);

  return (
    <div className="upload">
      <label
        className={`upload-zone ${labelClass}`.trim()}
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={onDrop}
      >
        <input
          ref={fileRef}
          type="file"
          accept=".xml,application/xml"
          disabled={busy}
          onChange={onInputChange}
        />
        {labelText}
      </label>
      {status === 'live' ? (
        <button
          className="btn ghost"
          onClick={() => {
            abort();
            reset();
          }}
        >
          ABORT
        </button>
      ) : upload.kind === 'uploaded' && status === 'complete' ? (
        <button className="btn" onClick={runCurrent}>
          ▶ RUN AGAIN
        </button>
      ) : upload.kind === 'uploaded' ? (
        <button className="btn" disabled={busy} onClick={runCurrent}>
          ▶ ENGAGE
        </button>
      ) : upload.kind === 'error' ? (
        <button className="btn ghost" onClick={() => setUpload({ kind: 'idle' })}>
          CLEAR
        </button>
      ) : (
        <button className="btn" disabled={busy} onClick={runSample}>
          ▶ RUN SAMPLE
        </button>
      )}
    </div>
  );
}

function zoneLabel(u: UploadState): string {
  switch (u.kind) {
    case 'idle':
      return 'drop XML · or click · or use sample →';
    case 'uploading':
      return `uploading ${u.name}…`;
    case 'uploaded':
      return `${u.name} · ${u.s3Key}`;
    case 'error':
      return `✖ ${u.message}`;
  }
}

function zoneClass(u: UploadState, drag: boolean): string {
  if (drag) return 'drag';
  if (u.kind === 'uploaded') return 'ok';
  if (u.kind === 'error') return 'error';
  return '';
}

function errMsg(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}
