// Backend event contract — mirrors what tribalance/app/TriBalanceAgent/main.py
// and nodes/_codegen.py emit through the Lambda proxy SSE stream.

export type NodeName =
  | 'fetch'
  | 'parse'
  | 'sleep'
  | 'activity'
  | 'synthesize'
  | 'plan';

export type Trend = 'up' | 'down' | 'stable';

export interface SleepMetrics {
  avg_duration_hr: number;
  avg_efficiency: number;
  trend: Trend;
}

export interface ActivityMetrics {
  avg_steps: number;
  avg_active_kcal: number;
  avg_exercise_min: number;
  trend: Trend;
}

export interface SleepPoint {
  date: string;
  asleep_hr: number;
  in_bed_hr: number;
  efficiency: number;
}

export interface ActivityPoint {
  date: string;
  steps: number;
  active_kcal: number;
  exercise_min: number;
}

export interface FinalReport {
  run_id: string;
  period: string;
  parse_summary?: {
    sleep_records: number;
    activity_records: number;
    period_days: number;
  };
  sleep_series?: SleepPoint[];
  activity_series?: ActivityPoint[];
  metrics?: {
    sleep?: { avg: Record<string, number>; trend: Trend; chart_s3_key: string };
    activity?: { avg: Record<string, number>; trend: Trend; chart_s3_key: string };
  };
  insights?: string[];
  plan?: string;
  generated_at?: string;
}

export type AgentEvent =
  | { event: 'run_started'; run_id: string; period: string }
  | { event: 'node_end'; node: NodeName }
  | { event: 'parsed_series'; sleep: SleepPoint[]; activity: ActivityPoint[] }
  | {
      event: 'code_generated';
      node: 'sleep' | 'activity';
      code: string;
      attempt: number;
    }
  | {
      event: 'code_result';
      node: 'sleep' | 'activity';
      stdout: string;
      stderr: string;
      ok: boolean;
      attempt: number;
    }
  | {
      event: 'metrics';
      node: 'sleep' | 'activity';
      metrics: SleepMetrics | ActivityMetrics;
    }
  | {
      event: 'artifact';
      node: string;
      s3_key: string;
      content_type: string;
    }
  | { event: 'complete'; report: FinalReport }
  | { event: 'error'; message: string; node?: string };
