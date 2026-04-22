import { useEffect, useState } from 'react';
import { useRunStore } from '../store/runStore';

function useClock(live: boolean) {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    if (!live) return;
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, [live]);
  return now;
}

function fmtKST(d: Date) {
  // 2026·04·23 07:44:00
  const pad = (n: number) => String(n).padStart(2, '0');
  const opts = { timeZone: 'Asia/Seoul' } as const;
  const parts = new Intl.DateTimeFormat('en-CA', {
    ...opts,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).formatToParts(d);
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? '';
  return `${get('year')}·${pad(+get('month'))}·${pad(+get('day'))} ${get('hour')}:${get('minute')}:${get('second')}`;
}

export function Topbar() {
  const status = useRunStore((s) => s.status);
  const runId = useRunStore((s) => s.runId);
  const startedAt = useRunStore((s) => s.startedAt);
  const clock = useClock(status === 'live');

  const dotClass = status === 'idle' ? 'idle'
    : status === 'live' ? ''
    : status === 'complete' ? 'done'
    : 'error';

  const latency =
    status === 'live' && startedAt
      ? `${((clock.getTime() - startedAt) / 1000).toFixed(2)}s`
      : status === 'complete' && startedAt
      ? `${((clock.getTime() - startedAt) / 1000).toFixed(2)}s`
      : '—';

  return (
    <div className="topbar">
      <div className="sys">
        <span className={`dot ${dotClass}`} />
        <span>ATLAS v.01</span>
        <span>·</span>
        <span>TRIBALANCE // WEEKLY HEALTH INTELLIGENCE</span>
      </div>
      <div className="coord">
        37.5665°N<b>/</b>126.9780°E<b>·</b>SEOUL<b>·</b>KST<b>·</b>{fmtKST(clock)}
      </div>
      <div className="run">
        <span>
          RUN<b>{runId ?? '—'}</b>
        </span>
        <span>
          STATE<b>{status.toUpperCase()}</b>
        </span>
        <span>
          LATENCY<b>{latency}</b>
        </span>
      </div>
    </div>
  );
}
