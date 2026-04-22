import { useRunStore } from '../store/runStore';
import { Panel } from './Panel';

export function PlanPanel() {
  const plan = useRunStore((s) => s.plan);

  return (
    <Panel id="F-01" title="PRESCRIPTION / WEEKLY" className="plan-panel">
      <div className="title">
        Weekly <em>prescription</em>
      </div>
      <div className={`text ${plan ? 'on' : ''}`.trim()}>
        {plan || '— waiting for synthesis & plan —'}
      </div>
    </Panel>
  );
}
