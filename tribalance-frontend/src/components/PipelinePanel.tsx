import { useRunStore } from '../store/runStore';
import type { NodeStatus } from '../store/runStore';
import type { NodeName } from '../store/events';
import { Panel } from './Panel';
import { Upload } from './Upload';

const STEPS: { key: NodeName; label: string }[] = [
  { key: 'fetch',       label: '01 · FETCH_S3' },
  { key: 'parse',       label: '02 · PARSE_XML' },
  { key: 'sleep',       label: '03 · SLEEP · CI' },
  { key: 'activity',    label: '04 · ACTIVITY · CI' },
  { key: 'synthesize',  label: '05 · SYNTHESIZE' },
  { key: 'plan',        label: '06 · PLAN' },
];

export function PipelinePanel() {
  const nodes = useRunStore((s) => s.nodes);

  return (
    <Panel id="B-01" title="PIPELINE / 6 NODES" className="status">
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
