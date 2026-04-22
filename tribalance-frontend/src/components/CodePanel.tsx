import { useRunStore } from '../store/runStore';
import { Panel } from './Panel';

export function CodePanel() {
  const currentNode = useRunStore((s) => s.currentCodeNode);
  const sleepCode = useRunStore((s) => s.sleepCode);
  const activityCode = useRunStore((s) => s.activityCode);

  const code = currentNode === 'activity' ? activityCode
    : currentNode === 'sleep' ? sleepCode
    : null;

  const title = code
    ? `NODE · ${currentNode} · ATTEMPT ${code.attempt} · code_interpreter.execute_isolated()`
    : 'NODE · waiting · code_interpreter.execute_isolated()';

  const displayCode = code ? code.code : '// waiting for a run…';
  const stdout = code?.stdout ?? '';
  const stderr = code?.stderr ?? '';
  const ok = code?.ok;

  const exitText = ok == null ? '—' : ok ? '0' : '!=0';

  return (
    <Panel id="C-01" title={title} className="code-panel">
      <div className="code-area">
        {highlight(displayCode)}
        {code && ok == null && <span className="caret" />}
      </div>
      <div className="stdbox">
        <div className="t">
          <span>
            STDOUT · exitCode=<em>{exitText}</em>
          </span>
          <span>{stderr ? 'stderr present' : ''}</span>
        </div>
        <pre>{stdout || '— waiting —'}</pre>
      </div>
    </Panel>
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
  // Process line-by-line to preserve structure. Comment handling first.
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
    // string literal
    if (c === '"' || c === "'") {
      const start = i;
      i++;
      while (i < part.length && !(part[i] === c && part[i - 1] !== '\\')) i++;
      i++;
      out.push(<span key={key++} className="s">{part.slice(start, i)}</span>);
      continue;
    }
    // identifier/keyword/call
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
    // everything else
    out.push(c);
    i++;
  }
  return out;
}
