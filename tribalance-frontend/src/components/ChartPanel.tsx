import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { useRunStore } from '../store/runStore';
import type { Trend } from '../store/events';
import { Panel } from './Panel';

type Which = 'sleep' | 'activity';

interface Props {
  which: Which;
}

export function ChartPanel({ which }: Props) {
  const sleepSeries = useRunStore((s) => s.sleepSeries);
  const activitySeries = useRunStore((s) => s.activitySeries);
  const sleepMetrics = useRunStore((s) => s.sleepMetrics);
  const activityMetrics = useRunStore((s) => s.activityMetrics);

  const isSleep = which === 'sleep';
  const id = isSleep ? 'D-01' : 'D-02';
  const title = isSleep ? 'FIG · SLEEP HOURS / WEEK' : 'FIG · DAILY STEPS / WEEK';
  const stroke = isSleep ? 'var(--warn)' : 'var(--primary)';
  const dataKey = isSleep ? 'asleep_hr' : 'steps';
  const data = isSleep
    ? sleepSeries.map((d) => ({ date: d.date.slice(5).replace('-', '·'), [dataKey]: d.asleep_hr }))
    : activitySeries.map((d) => ({ date: d.date.slice(5).replace('-', '·'), [dataKey]: d.steps }));

  const trend: Trend | null = isSleep
    ? sleepMetrics?.trend ?? null
    : activityMetrics?.trend ?? null;

  const metaRight = trend
    ? { text: `TREND · ${trend.toUpperCase()}`, stable: trend === 'stable' }
    : { text: 'AWAITING', stable: true };

  const rangeLabel = data.length > 0
    ? `${data.length} DATAPOINTS · ${data[0].date} → ${data[data.length - 1].date}`
    : '— no data yet —';

  return (
    <Panel id={id} title={title} className={`chart-panel ${data.length > 0 ? 'on' : ''}`.trim()}>
      <div className="chart-meta">
        <span>{rangeLabel}</span>
        <b className={metaRight.stable ? 'stable' : ''}>{metaRight.text}</b>
      </div>
      <div className="chart">
        {data.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 10, right: 16, bottom: 20, left: 0 }}>
              <CartesianGrid stroke="var(--grid-hi)" strokeDasharray="2 3" vertical={false} />
              <XAxis
                dataKey="date"
                stroke="var(--ink-mute)"
                tick={{ fill: 'var(--ink-dim)', fontSize: 10, fontFamily: 'var(--font-mono)' }}
                axisLine={{ stroke: 'var(--grid-hi)' }}
                tickLine={false}
              />
              <YAxis
                stroke="var(--ink-mute)"
                tick={{ fill: 'var(--ink-dim)', fontSize: 10, fontFamily: 'var(--font-mono)' }}
                axisLine={{ stroke: 'var(--grid-hi)' }}
                tickLine={false}
                width={38}
              />
              <Tooltip
                contentStyle={{
                  background: 'var(--panel-hi)',
                  border: '1px solid var(--grid-hi)',
                  borderRadius: 0,
                  fontFamily: 'var(--font-mono)',
                  fontSize: 11,
                  color: 'var(--ink)',
                }}
                labelStyle={{ color: 'var(--warn)', letterSpacing: '0.1em' }}
                formatter={(v: number) => (isSleep ? `${v}h` : v.toLocaleString())}
              />
              <Line
                type="monotone"
                dataKey={dataKey}
                stroke={stroke}
                strokeWidth={2}
                dot={{ fill: stroke, r: 3, strokeWidth: 0 }}
                activeDot={{ r: 5, fill: stroke }}
                isAnimationActive={true}
                animationDuration={600}
              />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div
            style={{
              height: '100%',
              display: 'grid',
              placeItems: 'center',
              fontFamily: 'var(--font-mono)',
              color: 'var(--ink-mute)',
              fontSize: 11,
              letterSpacing: '0.2em',
            }}
          >
            — NO DATA —
          </div>
        )}
      </div>
    </Panel>
  );
}
