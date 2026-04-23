import { PIPELINE_ORDER, useRunStore } from '../store/runStore';
import type { NodeName } from '../store/events';
import { Panel } from './Panel';

interface Props { zone?: string }

export function CodePanel({ zone }: Props = {}) {
  const currentNode = useRunStore((s) => s.currentCodeNode);
  const sleepCode = useRunStore((s) => s.sleepCode);
  const activityCode = useRunStore((s) => s.activityCode);
  const status = useRunStore((s) => s.status);
  const nodes = useRunStore((s) => s.nodes);

  const code = currentNode === 'activity' ? activityCode
    : currentNode === 'sleep' ? sleepCode
    : null;

  const activeNode = PIPELINE_ORDER.find((n) => nodes[n] === 'active') ?? null;

  // Three modes:
  //  code       → real generated code + stdout  (sleep/activity CI nodes)
  //  live-wait  → live run but no code yet (fetch/parse/synth/plan or pre-codegen)
  //  idle       → nothing running
  const mode: 'code' | 'live-wait' | 'idle' =
    code ? 'code' : status === 'live' ? 'live-wait' : 'idle';

  const title =
    mode === 'code' && code
      ? `NODE · ${currentNode} · ATTEMPT ${code.attempt} · code_interpreter.execute_isolated()`
      : mode === 'live-wait' && activeNode
      ? `NODE · ${activeNode} · ${PHASE_HINT[activeNode]}`
      : 'NODE · waiting · code_interpreter.execute_isolated()';

  return (
    <Panel id="C-01" title={title} zone={zone} className="code-panel">
      {mode === 'code' && code ? (
        <>
          <div className="code-area">
            {highlight(code.code)}
            {code.ok == null && <span className="caret" />}
          </div>
          <div className="stdbox">
            <div className="t">
              <span>
                STDOUT · exitCode=<em>{code.ok == null ? '—' : code.ok ? '0' : '!=0'}</em>
              </span>
              <span>{code.stderr ? 'stderr present' : ''}</span>
            </div>
            <pre>{code.stdout || '— waiting —'}</pre>
          </div>
        </>
      ) : mode === 'live-wait' ? (
        <FakeLog node={activeNode} />
      ) : (
        <div className="code-area">
          {highlight('// waiting for a run…')}
        </div>
      )}
    </Panel>
  );
}

/* ------------------------ live-wait placeholder ------------------------ */

const PHASE_HINT: Record<NodeName, string> = {
  fetch: 'downloading healthkit export…',
  parse: 'parsing export.xml…',
  sleep: 'generating code…',
  activity: 'generating code…',
  synthesize: 'composing insights…',
  plan: 'drafting prescription…',
};

const NODE_LOG: Record<NodeName, string[]> = {
  fetch: [
    '> opening bedrock-agentcore runtime session',
    '> s3://tribalance-input · get_object',
    '> streaming bytes · gzip decompress',
    '> handoff → parse_xml',
  ],
  parse: [
    '> reading apple-health export.xml',
    '> scanning HKSleepAnalysis records',
    '> scanning HKQuantityTypeIdentifier (steps, energy, exercise)',
    '> aggregating per-day series',
  ],
  sleep: [
    '> picking sleep analysis task',
    '> prompting claude-sonnet-4-6 (attempt 1)',
    '> opening code_interpreter.execute_isolated',
    '> forwarding series payload…',
  ],
  activity: [
    '> picking activity analysis task',
    '> prompting claude-sonnet-4-6 (attempt 1)',
    '> opening code_interpreter.execute_isolated',
    '> forwarding series payload…',
  ],
  synthesize: [
    '> composing insights (temperature=0.2)',
    '> scoring severity · low / watch / high',
    '> shortlisting 6 actionable items',
  ],
  plan: [
    '> drafting weekly prescription',
    '> aligning with metrics & insights',
    '> finalizing summary',
  ],
};

function FakeLog({ node }: { node: NodeName | null }) {
  if (!node) {
    return <div className="code-area">{highlight('// initializing…')}<span className="caret" /></div>;
  }
  const lines = NODE_LOG[node];
  return (
    <div className="code-area fake-log" key={node}>
      {lines.map((ln, i) => (
        <div
          key={i}
          className="fake-log-line"
          style={{ animationDelay: `${i * 0.55}s` }}
        >
          {ln}
        </div>
      ))}
      <div
        className="fake-log-line heartbeat"
        style={{ animationDelay: `${lines.length * 0.55}s` }}
      >
        &gt; heartbeat <span className="caret" />
      </div>
    </div>
  );
}

/* Minimal Python syntax tokenizer. Not perfect; ATLAS-flavored. */
const KEYWORDS = new Set([
  'import', 'from', 'as', 'def', 'return', 'if', 'elif', 'else', 'for',
  'while', 'in', 'not', 'and', 'or', 'is', 'True', 'False', 'None',
  'try', 'except', 'finally', 'with', 'lambda', 'pass', 'continue',
  'break', 'class', 'raise',
]);

function highlight(src: string): React.ReactNode {
  const lines = src.split('\n');
  return lines.map((line, i) => (
    <span key={i}>
      {highlightLine(line)}
      {'\n'}
    </span>
  ));
}

function highlightLine(line: string): React.ReactNode {
  const hashIdx = indexOfUnquotedHash(line);
  if (hashIdx !== -1) {
    return (
      <>
        {tokenize(line.slice(0, hashIdx))}
        <span className="c">{line.slice(hashIdx)}</span>
      </>
    );
  }
  return tokenize(line);
}

function indexOfUnquotedHash(line: string): number {
  let inStr: string | null = null;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (inStr) {
      if (c === inStr && line[i - 1] !== '\\') inStr = null;
      continue;
    }
    if (c === '"' || c === "'") { inStr = c; continue; }
    if (c === '#') return i;
  }
  return -1;
}

function tokenize(part: string): React.ReactNode {
  const out: React.ReactNode[] = [];
  let i = 0;
  let key = 0;
  while (i < part.length) {
    const c = part[i];
    if (c === '"' || c === "'") {
      const start = i;
      i++;
      while (i < part.length && !(part[i] === c && part[i - 1] !== '\\')) i++;
      i++;
      out.push(<span key={key++} className="s">{part.slice(start, i)}</span>);
      continue;
    }
    if (/[A-Za-z_]/.test(c)) {
      const start = i;
      while (i < part.length && /[A-Za-z0-9_]/.test(part[i])) i++;
      const word = part.slice(start, i);
      if (KEYWORDS.has(word)) {
        out.push(<span key={key++} className="k">{word}</span>);
      } else if (part[i] === '(') {
        out.push(<span key={key++} className="f">{word}</span>);
      } else {
        out.push(word);
      }
      continue;
    }
    out.push(c);
    i++;
  }
  return out;
}
