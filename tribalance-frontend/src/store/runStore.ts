import { create } from 'zustand';
import type {
  AgentEvent,
  NodeName,
  SleepMetrics,
  ActivityMetrics,
  SleepPoint,
  ActivityPoint,
} from './events';

export type NodeStatus = 'idle' | 'active' | 'done' | 'error';

export interface CodeState {
  code: string;
  attempt: number;
  stdout: string;
  stderr: string;
  ok: boolean | null;
  execTime?: number;
}

export type RunStatus = 'idle' | 'live' | 'complete' | 'error';

interface RunState {
  // meta
  runId: string | null;
  status: RunStatus;
  errorMessage: string | null;
  period: string | null;
  startedAt: number | null;

  // per-node status
  nodes: Record<NodeName, NodeStatus>;

  // live code panel (sleep/activity share it; last node wins)
  currentCodeNode: 'sleep' | 'activity' | null;
  sleepCode: CodeState | null;
  activityCode: CodeState | null;

  // time series (from parse)
  sleepSeries: SleepPoint[];
  activitySeries: ActivityPoint[];

  // metrics (from CI nodes)
  sleepMetrics: SleepMetrics | null;
  activityMetrics: ActivityMetrics | null;

  // output
  insights: string[];
  plan: string;

  // actions
  reset: () => void;
  dispatch: (event: AgentEvent) => void;
}

const INITIAL_NODES: Record<NodeName, NodeStatus> = {
  fetch: 'idle',
  parse: 'idle',
  sleep: 'idle',
  activity: 'idle',
  synthesize: 'idle',
  plan: 'idle',
};

const PIPELINE_ORDER: NodeName[] = [
  'fetch',
  'parse',
  'sleep',
  'activity',
  'synthesize',
  'plan',
];

export const useRunStore = create<RunState>((set) => ({
  runId: null,
  status: 'idle',
  errorMessage: null,
  period: null,
  startedAt: null,
  nodes: { ...INITIAL_NODES },
  currentCodeNode: null,
  sleepCode: null,
  activityCode: null,
  sleepSeries: [],
  activitySeries: [],
  sleepMetrics: null,
  activityMetrics: null,
  insights: [],
  plan: '',

  reset: () =>
    set({
      runId: null,
      status: 'idle',
      errorMessage: null,
      period: null,
      startedAt: null,
      nodes: { ...INITIAL_NODES },
      currentCodeNode: null,
      sleepCode: null,
      activityCode: null,
      sleepSeries: [],
      activitySeries: [],
      sleepMetrics: null,
      activityMetrics: null,
      insights: [],
      plan: '',
    }),

  dispatch: (e) =>
    set((s) => {
      switch (e.event) {
        case 'run_started':
          return {
            runId: e.run_id,
            status: 'live' as RunStatus,
            period: e.period,
            startedAt: Date.now(),
            nodes: { ...INITIAL_NODES, fetch: 'active' },
          };

        case 'node_end': {
          const nodes = { ...s.nodes, [e.node]: 'done' as NodeStatus };
          // mark next node active
          const idx = PIPELINE_ORDER.indexOf(e.node);
          if (idx >= 0 && idx + 1 < PIPELINE_ORDER.length) {
            const next = PIPELINE_ORDER[idx + 1];
            if (nodes[next] === 'idle') nodes[next] = 'active';
          }
          return { nodes };
        }

        case 'parsed_series':
          return { sleepSeries: e.sleep, activitySeries: e.activity };

        case 'code_generated': {
          const patch: CodeState = {
            code: e.code,
            attempt: e.attempt,
            stdout: '',
            stderr: '',
            ok: null,
          };
          if (e.node === 'sleep')
            return { sleepCode: patch, currentCodeNode: 'sleep' };
          return { activityCode: patch, currentCodeNode: 'activity' };
        }

        case 'code_result': {
          if (e.node === 'sleep' && s.sleepCode) {
            return {
              sleepCode: {
                ...s.sleepCode,
                stdout: e.stdout,
                stderr: e.stderr,
                ok: e.ok,
              },
            };
          }
          if (e.node === 'activity' && s.activityCode) {
            return {
              activityCode: {
                ...s.activityCode,
                stdout: e.stdout,
                stderr: e.stderr,
                ok: e.ok,
              },
            };
          }
          return {};
        }

        case 'metrics':
          if (e.node === 'sleep')
            return { sleepMetrics: e.metrics as SleepMetrics };
          return { activityMetrics: e.metrics as ActivityMetrics };

        case 'artifact':
          // Not used with recharts chart rendering. Kept for future
          // "view raw PNG" feature. No state change.
          return {};

        case 'complete': {
          const r = e.report;
          return {
            status: 'complete' as RunStatus,
            insights: r.insights ?? s.insights,
            plan: r.plan ?? s.plan,
          };
        }

        case 'error':
          return {
            status: 'error' as RunStatus,
            errorMessage: e.message,
          };

        default:
          return {};
      }
    }),
}));
