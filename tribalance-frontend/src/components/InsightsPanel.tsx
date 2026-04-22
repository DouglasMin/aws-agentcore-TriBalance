import { useRunStore } from '../store/runStore';
import { Panel } from './Panel';

// Simple code-prefix rotation for visual tagging; real severity classification
// can come from the backend later.
const CODES = ['SL-01', 'AC-02', 'EN-03', 'RH-04', 'OB-05', 'DB-06'];

interface Props { zone?: string }

export function InsightsPanel({ zone }: Props = {}) {
  const insights = useRunStore((s) => s.insights);

  return (
    <Panel id="E-01" title="INSIGHTS / SYNTHESIZED" zone={zone} className="insights-panel">
      <div className="list">
        {insights.length === 0 ? (
          <div
            style={{
              color: 'var(--ink-mute)',
              fontFamily: 'var(--font-mono)',
              fontSize: 11,
              letterSpacing: '0.2em',
              padding: '10px 0',
            }}
          >
            — NO INSIGHTS YET —
          </div>
        ) : (
          insights.map((text, i) => {
            const sev = /\b(low|high|drop|exceed|risk|warning|watch)\b/i.test(text)
              ? 'WATCH'
              : 'OK';
            return (
              <div key={i} className="ins on">
                <div className="c">{CODES[i % CODES.length]}</div>
                <div className="t">{text}</div>
                <div
                  className="sev"
                  style={{ color: sev === 'WATCH' ? 'var(--warn)' : 'var(--success)' }}
                >
                  {sev}
                </div>
              </div>
            );
          })
        )}
      </div>
    </Panel>
  );
}
