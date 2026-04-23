import { useRunStore } from '../store/runStore';

interface Copy {
  label: string;
  hint: string;
}

// Tailored copy per backend error kind. Keep short: banner is one line.
const COPY: Record<string, Copy> = {
  invalid_input: {
    label: 'INVALID INPUT',
    hint: 'missing s3_key in payload. If this persists, reload the page.',
  },
  empty_data: {
    label: 'NO DATA',
    hint:
      'the export had 0 matching sleep/activity records. Is it an Apple Health export.xml with Apple Watch data?',
  },
  agentcore_invoke_failed: {
    label: 'AGENT UNREACHABLE',
    hint: 'bedrock-agentcore invocation failed. Check the runtime is deployed and the Lambda role has InvokeAgentRuntime.',
  },
  agentcore_no_stream: {
    label: 'NO STREAM',
    hint: 'AgentCore returned without a response body. Transient — retry.',
  },
  stream_drop: {
    label: 'STREAM DROPPED',
    hint: 'the connection closed mid-run. Retry; if it repeats, Lambda may be timing out.',
  },
  access_denied: {
    label: 'ACCESS DENIED',
    hint: 'IAM rejected an action. Check Lambda role permissions for S3 and AgentCore.',
  },
  s3_not_found: {
    label: 'S3 KEY NOT FOUND',
    hint: 'the uploaded XML was not found in the input bucket. Try uploading again.',
  },
  timeout: {
    label: 'TIMEOUT',
    hint: 'a node exceeded its deadline. Large exports may need a bigger Lambda timeout.',
  },
  code_interpreter_failure: {
    label: 'CODE INTERPRETER FAILED',
    hint: 'the sandboxed execution errored out. See C-01 stderr for the actual traceback.',
  },
  graph_failure: {
    label: 'AGENT FAILED',
    hint: 'the agent graph aborted. See message below; retry once.',
  },
  network: {
    label: 'NETWORK',
    hint: 'could not reach the proxy. Check VITE_PROXY_URL and that the Function URL is deployed.',
  },
};

export function ErrorBanner() {
  const msg = useRunStore((s) => s.errorMessage);
  const kind = useRunStore((s) => s.errorKind);
  const reset = useRunStore((s) => s.reset);

  if (!msg) return null;

  const copy = (kind && COPY[kind]) || {
    label: 'ERROR',
    hint: 'unexpected failure; try again.',
  };

  return (
    <div className="err-banner">
      <div className="err-left">
        <span className="err-tag">{copy.label}</span>
        <span className="err-hint">{copy.hint}</span>
      </div>
      <div className="err-right">
        <code className="err-msg">{msg}</code>
        <button type="button" className="err-dismiss" onClick={reset}>
          DISMISS
        </button>
      </div>
    </div>
  );
}
