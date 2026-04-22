import { useRunStore } from './store/runStore';
import { Topbar } from './components/Topbar';
import { VitalPanel } from './components/VitalPanel';
import { PipelinePanel } from './components/PipelinePanel';
import { CodePanel } from './components/CodePanel';
import { ChartPanel } from './components/ChartPanel';
import { InsightsPanel } from './components/InsightsPanel';
import { PlanPanel } from './components/PlanPanel';
import './styles/atlas.css';

export default function App() {
  const sleepMetrics = useRunStore((s) => s.sleepMetrics);
  const activityMetrics = useRunStore((s) => s.activityMetrics);
  const errorMessage = useRunStore((s) => s.errorMessage);

  return (
    <>
      <Topbar />
      {errorMessage && (
        <div
          style={{
            padding: '10px 20px',
            background: 'rgba(239,68,68,0.1)',
            borderBottom: '1px solid var(--danger)',
            color: 'var(--danger)',
            fontFamily: 'var(--font-mono)',
            fontSize: 11,
            letterSpacing: '0.1em',
          }}
        >
          ERROR · {errorMessage}
        </div>
      )}
      <div className="atlas">
        {/* Row 1 — KPIs + Pipeline */}
        <VitalPanel
          zone="z-vital-1"
          id="A-01"
          title="SLEEP DURATION"
          primary
          value={sleepMetrics?.avg_duration_hr ?? null}
          label="Hours asleep / night"
          kind="hr"
        />
        <VitalPanel
          zone="z-vital-1"
          id="A-02"
          title="SLEEP EFFICIENCY"
          value={sleepMetrics ? sleepMetrics.avg_efficiency * 100 : null}
          label="asleep ÷ in bed"
          kind="pct"
        />
        <VitalPanel
          zone="z-vital-1"
          id="A-03"
          title="DAILY STEPS"
          value={activityMetrics?.avg_steps ?? null}
          label="5-day mean"
          kind="int"
        />
        <VitalPanel
          zone="z-vital-1"
          id="A-04"
          title="ACTIVE BURN"
          value={activityMetrics?.avg_active_kcal ?? null}
          label="kcal / day"
          kind="int"
        />
        <PipelinePanel zone="z-status" />

        {/* Row 2+ — Code (spans 4 rows) + Sleep chart (2 rows) */}
        <CodePanel zone="z-code" />
        <ChartPanel zone="z-chart" which="sleep" />
        {/* Activity chart fills the next chart slot */}
        <ChartPanel zone="z-chart" which="activity" />

        {/* Final row — Insights + Plan */}
        <InsightsPanel zone="z-insights" />
        <PlanPanel zone="z-plan" />
      </div>
    </>
  );
}
