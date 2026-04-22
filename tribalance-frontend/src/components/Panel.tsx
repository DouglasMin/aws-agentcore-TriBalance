import type { ReactNode } from 'react';

interface Props {
  id: string;           // coord id like "A-01"
  title: string;        // header title
  zone?: string;        // "z-vital-1", "z-code", ...  (grid placement)
  className?: string;   // extra classes (vital, code-panel, primary, ...)
  children: ReactNode;
}

export function Panel({ id, title, zone, className = '', children }: Props) {
  const classes = ['panel', zone, className].filter(Boolean).join(' ');
  return (
    <div className={classes}>
      <div className="hdr">
        <span className="id">{id}</span>
        <span>{title}</span>
      </div>
      {children}
    </div>
  );
}
