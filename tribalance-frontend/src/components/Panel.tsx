import type { ReactNode } from 'react';

interface Props {
  id: string;           // coord id like "A-01"
  title: string;        // header title
  className?: string;   // extra classes (vital, code-panel, etc.)
  children: ReactNode;
}

export function Panel({ id, title, className = '', children }: Props) {
  return (
    <div className={`panel ${className}`.trim()}>
      <div className="hdr">
        <span className="id">{id}</span>
        <span>{title}</span>
      </div>
      {children}
    </div>
  );
}
