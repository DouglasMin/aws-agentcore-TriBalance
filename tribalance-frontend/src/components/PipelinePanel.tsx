import { PIPELINE_ORDER, useRunStore } from '../store/runStore';
import type { NodeStatus } from '../store/runStore';
import type { NodeName } from '../store/events';
import { Panel } from './Panel';
import { Upload } from './Upload';

const STEPS: { key: NodeName; short: string; label: string }[] = [
  { key: 'fetch',       short: 'FETCH_S3',      label: '01 · FETCH_S3' },
  { key: 'parse',       short: 'PARSE_XML',     label: '02 · PARSE_XML' },
  { key: 'sleep',       short: 'SLEEP · CI',    label: '03 · SLEEP · CI' },
  { key: 'activity',    short: 'ACTIVITY · CI', label: '04 · ACTIVITY · CI' },
  { key: 'synthesize',  short: 'SYNTHESIZE',    label: '05 · SYNTHESIZE' },
  { key: 'plan',        short: 'PLAN',          label: '06 · PLAN' },
];

interface Props { zone?: string }

export function PipelinePanel({ zone }: Props = {}) {
  const nodes = useRunStore((s) => s.nodes);
  const status = useRunStore((s) => s.status);
  const runId = useRunStore((s) => s.runId);

  const connecting = status === 'live' && !runId;

  const activeKey = PIPELINE_ORDER.find((n) => nodes[n] === 'active') ?? null;
  const doneCount = PIPELINE_ORDER.filter((n) => nodes[n] === 'done').length;
  const activeIdx = activeKey ? PIPELINE_ORDER.indexOf(activeKey) + 1 : doneCount;
  const progress = String(activeIdx || doneCount).padStart(2, '0');
  const activeShort = activeKey
    ? STEPS.find((s) => s.key === activeKey)?.short ?? ''
    : '';

  const title =
    status === 'live' && activeKey
      ? `PIPELINE · ${progress}/06 · ${activeShort}`
      : status === 'complete'
      ? 'PIPELINE · 06/06 · COMPLETE'
      : status === 'error'
      ? 'PIPELINE · HALTED'
      : 'PIPELINE / 6 NODES';

  return (
    <Panel id="B-01" title={title} zone={zone} className="status">
      {connecting && (
        <div className="connecting">
          <span className="connecting-dot" />
          <span>CONNECTING TO AGENTCORE…</span>
        </div>
      )}
      <div className="pipe">
        {STEPS.map(({ key, label }) => {
          const s = nodes[key];
          return (
            <div key={key} className={`step ${stepClass(s)}`}>
              <span className="d" />
              <span>{label}</span>
              <span className="t">{s === 'idle' ? '—' : s.toUpperCase()}</span>
            </div>
          );
        })}
      </div>
      <Upload />
    </Panel>
  );
}

function stepClass(s: NodeStatus): string {
  if (s === 'active') return 'on';
  if (s === 'done') return 'done';
  return '';
}
