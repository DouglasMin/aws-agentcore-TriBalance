import { useEffect, useRef, useState } from 'react';
import { Panel } from './Panel';

type Kind = 'hr' | 'pct' | 'int';

interface Props {
  id: string;                  // A-01, A-02, ...
  title: string;
  value: number | null;
  label: string;
  kind: Kind;
  primary?: boolean;
  delta?: string | null;
  deltaBad?: boolean;
}

export function VitalPanel({
  id, title, value, label, kind, primary, delta, deltaBad,
}: Props) {
  const [shown, setShown] = useState(0);
  const startRef = useRef<number | null>(null);

  useEffect(() => {
    if (value == null) { setShown(0); startRef.current = null; return; }
    const target = value;
    const dur = 900;
    let raf = 0;
    const tick = (t: number) => {
      if (startRef.current == null) startRef.current = t;
      const p = Math.min(1, (t - startRef.current) / dur);
      const eased = 1 - Math.pow(1 - p, 3);
      setShown(target * eased);
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      startRef.current = null;
    };
  }, [value]);

  const text = value == null ? '—' : format(shown, kind);
  const unit = value == null ? null : unitFor(kind);

  return (
    <Panel id={id} title={title} className={`vital ${primary ? 'primary' : ''}`.trim()}>
      <div className="v">
        {text}
        {unit && <span className="u">{unit}</span>}
      </div>
      <div className="l">{label}</div>
      {delta && <div className={`delta ${deltaBad ? 'bad' : ''}`.trim()}>{delta}</div>}
    </Panel>
  );
}

function format(v: number, kind: Kind): string {
  if (kind === 'hr') return v.toFixed(1);
  if (kind === 'pct') return String(Math.round(v));
  return Math.round(v).toLocaleString();
}

function unitFor(kind: Kind): string | null {
  if (kind === 'hr') return 'h';
  if (kind === 'pct') return '%';
  return null;
}
