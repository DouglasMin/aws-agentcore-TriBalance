import { useRef, useState } from 'react';
import { useInvoke } from '../hooks/useSSE';
import { useRunStore } from '../store/runStore';

const PROXY_URL = import.meta.env.VITE_PROXY_URL || '';

interface PresignResponse {
  url: string;
  key: string;
  expires_in: number;
}

export function Upload() {
  const { invoke, abort } = useInvoke();
  const reset = useRunStore((s) => s.reset);
  const status = useRunStore((s) => s.status);
  const fileRef = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const [filename, setFilename] = useState<string | null>(null);
  const [msg, setMsg] = useState<string>('drop XML here · or click');
  const [uploading, setUploading] = useState(false);

  async function handleFile(f: File) {
    setFilename(f.name);
    setMsg(`uploading ${(f.size / 1024).toFixed(0)} KB…`);
    setUploading(true);

    if (!PROXY_URL) {
      setMsg('VITE_PROXY_URL not set');
      setUploading(false);
      return;
    }

    // 1. ask proxy for a presigned PUT URL
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
      if (!resp.ok) throw new Error(`presign: ${resp.status}`);
      pre = (await resp.json()) as PresignResponse;
    } catch (err) {
      setMsg(`presign failed: ${String(err)}`);
      setUploading(false);
      return;
    }

    // 2. PUT to S3
    try {
      const putResp = await fetch(pre.url, {
        method: 'PUT',
        headers: { 'Content-Type': f.type || 'application/xml' },
        body: f,
      });
      if (!putResp.ok) throw new Error(`PUT: ${putResp.status}`);
    } catch (err) {
      setMsg(`upload failed: ${String(err)}`);
      setUploading(false);
      return;
    }

    setMsg(`uploaded · ${pre.key}`);
    setUploading(false);

    // 3. invoke agent
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

  const busy = status === 'live' || uploading;

  return (
    <div className="upload">
      <label
        className={`upload-zone ${drag ? 'drag' : ''} ${filename && !uploading ? 'ok' : ''}`.trim()}
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
        {filename ? `${filename}` : msg}
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
      ) : (
        <button
          className="btn"
          disabled={busy}
          onClick={() => {
            // Quick demo path: if no file yet, kick off with the bundled sample.
            if (!filename) {
              setMsg('using s3 sample');
              void invoke({
                s3_key: 'samples/export_sample.xml',
                week_start: new Date().toISOString().slice(0, 10),
              });
              return;
            }
          }}
        >
          {status === 'complete' ? '▶ RUN AGAIN' : '▶ ENGAGE'}
        </button>
      )}
    </div>
  );
}
