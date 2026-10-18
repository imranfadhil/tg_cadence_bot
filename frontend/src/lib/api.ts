import { getTelegramInitData } from './telegram';

export type HorizonLevel = 'ANNUAL' | 'MONTHLY' | 'WEEKLY' | 'DAILY';
export type GoalStatus = 'ACTIVE' | 'PAUSED' | 'COMPLETED' | 'ARCHIVED';
export type CheckInResult = 'DONE' | 'PARTIAL' | 'MISSED' | 'REST_DAY';

export interface MomentumSummary {
  user_id: number;
  first_name: string;
  timezone: string;
  coach_intensity: 'STANDARD' | 'HIGH_RIGOR' | 'RECOVERY_MODE';
  morning_brief_time: string;
  evening_pulse_time: string;
  cadence_score: number;
  active_streak_days: number;
  completed_today: number;
  total_today: number;
  earned_silence_count: number;
  bargain_active_count: number;
  missed_yesterday_unlogged: boolean;
}

export interface TodayGoalCard {
  id: string;
  title: string;
  category?: string | null;
  parent_weekly_title?: string | null;
  parent_monthly_title?: string | null;
  parent_annual_title?: string | null;
  breadcrumb: string;
  target_value: number;
  current_value: number;
  streak_count: number;
  consecutive_misses: number;
  earned_silence: boolean;
  needs_bargain: boolean;
  status: GoalStatus;
  today_result?: CheckInResult | null;
  today_note?: string | null;
}

export interface TodayViewResponse {
  summary: MomentumSummary;
  date: string;
  goals: TodayGoalCard[];
}

export interface GoalTreeNode {
  id: string;
  parent_id?: string | null;
  horizon: HorizonLevel;
  category?: string | null;
  title: string;
  metric_type: 'BOOLEAN' | 'NUMERIC' | 'DURATION';
  target_value: number;
  current_value: number;
  progress_pct: number;
  streak_count: number;
  consecutive_misses: number;
  earned_silence: boolean;
  needs_bargain: boolean;
  status: GoalStatus;
  today_result?: CheckInResult | null;
  children: GoalTreeNode[];
}

export interface ScorecardDay {
  date: string;
  label: string;
  completion_pct: number;
  done_count: number;
  partial_count: number;
  missed_count: number;
}

export interface HorizonAuditItem {
  monthly_goal_id: string;
  monthly_title: string;
  annual_title: string;
  category: string;
  weekly_execution_pct: number;
  monthly_milestone_pct: number;
  status_label: 'ON_TRACK' | 'SLIPPING' | 'BLOCKER';
}

export interface ScorecardResponse {
  summary: MomentumSummary;
  weekly_days: ScorecardDay[];
  horizon_audit: HorizonAuditItem[];
  diagnostic_question: string;
}

export interface CascadeProposal {
  coach_summary: string;
  annual_goals: {
    title: string;
    category: string;
    monthly_targets: {
      title: string;
      weekly_milestones: {
        title: string;
        target_metric: string;
        daily_actions: {
          title: string;
          frequency_per_week: number;
        }[];
      }[];
    }[];
  }[];
}

export interface CheckInToggleResponse {
  goal: TodayGoalCard;
  summary: MomentumSummary;
  coach_feedback: string;
  bargain_triggered: boolean;
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers || {});
  headers.set('Content-Type', 'application/json');
  const initData = getTelegramInitData();
  if (initData) {
    headers.set('X-Telegram-Init-Data', initData);
  }

  const response = await fetch(path, {
    ...init,
    headers,
  });

  if (!response.ok) {
    const errText = await response.text();
    throw new Error(errText || `HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const cadenceApi = {
  getTodayView: () => apiFetch<TodayViewResponse>('/api/checkins/today'),

  toggleCheckIn: (payload: {
    goal_id: string;
    result: CheckInResult;
    user_note?: string;
  }) =>
    apiFetch<CheckInToggleResponse>('/api/checkins/toggle', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  resolveBargain: (payload: {
    goal_id: string;
    action: 'MICRO_5M' | 'SCALE_BACK_25' | 'PAUSE_MONDAY';
  }) =>
    apiFetch<{
      goal_id: string;
      action: string;
      coach_message: string;
      updated_title: string;
      updated_target: number;
      updated_status: GoalStatus;
    }>('/api/checkins/bargain', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  resolveDiagnostic: (action: 'LOG_YESTERDAY_ALL' | 'CRAZY_DAY_RESUME' | 'ADJUST_WEEKLY_LOAD') =>
    apiFetch<{ message: string }>('/api/checkins/diagnostic', {
      method: 'POST',
      body: JSON.stringify({ action }),
    }),

  getGoalsTree: () => apiFetch<GoalTreeNode[]>('/api/goals/tree'),

  updateGoalNode: (
    goalId: string,
    payload: {
      title: string;
      horizon: HorizonLevel;
      target_value: number;
      status: GoalStatus;
      category?: string | null;
    }
  ) =>
    apiFetch<GoalTreeNode[]>(`/api/goals/${goalId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  createGoalNode: (payload: {
    title: string;
    horizon: HorizonLevel;
    parent_id?: string | null;
    category?: string | null;
    target_value: number;
  }) =>
    apiFetch<GoalTreeNode[]>('/api/goals', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  getScorecard: () => apiFetch<ScorecardResponse>('/api/scorecard'),

  decomposeOnboarding: (text: string, lessAggressive = false) =>
    apiFetch<CascadeProposal>('/api/onboarding/decompose', {
      method: 'POST',
      body: JSON.stringify({ text, less_aggressive: lessAggressive }),
    }),

  scaleDownProposal: (proposal: CascadeProposal) =>
    apiFetch<CascadeProposal>('/api/onboarding/scale-down', {
      method: 'POST',
      body: JSON.stringify(proposal),
    }),

  lockInProposal: (proposal: CascadeProposal) =>
    apiFetch<GoalTreeNode[]>('/api/onboarding/lock-in', {
      method: 'POST',
      body: JSON.stringify(proposal),
    }),
};

