import React, { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CheckCircle2, Info, ShieldAlert } from 'lucide-react';
import {
  CheckInResult,
  GoalStatus,
  HorizonLevel,
  cadenceApi,
} from './lib/api';
import { initTelegramLightTheme, triggerHaptic } from './lib/telegram';
import { MomentumHeader } from './components/MomentumHeader';
import { HorizonTabs, MainViewTab } from './components/HorizonTabs';
import { TodayCheckInCard } from './components/TodayCheckInCard';
import { GoalCascadeTree } from './components/GoalCascadeTree';
import { ScorecardView } from './components/ScorecardView';
import { OnboardingModal } from './components/OnboardingModal';

export const App: React.FC = () => {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<MainViewTab>('TODAY');
  const [horizonFilter, setHorizonFilter] = useState<HorizonLevel | 'ALL'>('ALL');
  const [onboardingOpen, setOnboardingOpen] = useState(false);
  const [coachBanner, setCoachBanner] = useState<string | null>(null);

  useEffect(() => {
    initTelegramLightTheme();
  }, []);

  const todayQuery = useQuery({
    queryKey: ['todayView'],
    queryFn: cadenceApi.getTodayView,
  });

  const treeQuery = useQuery({
    queryKey: ['goalsTree'],
    queryFn: cadenceApi.getGoalsTree,
  });

  const scorecardQuery = useQuery({
    queryKey: ['scorecard'],
    queryFn: cadenceApi.getScorecard,
  });

  const refreshAll = () => {
    queryClient.invalidateQueries({ queryKey: ['todayView'] });
    queryClient.invalidateQueries({ queryKey: ['goalsTree'] });
    queryClient.invalidateQueries({ queryKey: ['scorecard'] });
  };

  const toggleMutation = useMutation({
    mutationFn: ({ goalId, result }: { goalId: string; result: CheckInResult }) =>
      cadenceApi.toggleCheckIn({ goal_id: goalId, result }),
    onSuccess: (data) => {
      setCoachBanner(data.coach_feedback);
      refreshAll();
    },
  });

  const bargainMutation = useMutation({
    mutationFn: ({
      goalId,
      action,
    }: {
      goalId: string;
      action: 'MICRO_5M' | 'SCALE_BACK_25' | 'PAUSE_MONDAY';
    }) => cadenceApi.resolveBargain({ goal_id: goalId, action }),
    onSuccess: (data) => {
      setCoachBanner(data.coach_message);
      refreshAll();
    },
  });

  const diagnosticMutation = useMutation({
    mutationFn: (
      action: 'LOG_YESTERDAY_ALL' | 'CRAZY_DAY_RESUME' | 'ADJUST_WEEKLY_LOAD'
    ) => cadenceApi.resolveDiagnostic(action),
    onSuccess: (data) => {
      setCoachBanner(data.message);
      refreshAll();
    },
  });

  const updateNodeMutation = useMutation({
    mutationFn: ({
      goalId,
      payload,
    }: {
      goalId: string;
      payload: {
        title: string;
        horizon: HorizonLevel;
        target_value: number;
        status: GoalStatus;
        category?: string | null;
      };
    }) => cadenceApi.updateGoalNode(goalId, payload),
    onSuccess: () => {
      setCoachBanner('Goal node calibrated in Studio.');
      refreshAll();
    },
  });

  const createNodeMutation = useMutation({
    mutationFn: cadenceApi.createGoalNode,
    onSuccess: () => {
      setCoachBanner('New node added to Cascade Tree.');
      refreshAll();
    },
  });

  const summary = todayQuery.data?.summary;
  const goals = todayQuery.data?.goals || [];

  return (
    <div className="min-h-screen bg-[#FAFAFA] text-[#18181B] pb-16">
      {/* Top Momentum Bar */}
      <MomentumHeader
        summary={summary}
        onOpenOnboarding={() => setOnboardingOpen(true)}
      />

      {/* Segmented Control & Horizon Switcher */}
      <HorizonTabs
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        horizonFilter={horizonFilter}
        onSelectHorizonFilter={setHorizonFilter}
        bargainCount={summary?.bargain_active_count || 0}
      />

      {/* Main Content Container */}
      <main className="max-w-xl mx-auto px-4 pt-2 space-y-3">
        {/* Live Coach Telemetry Toast / Banner */}
        {coachBanner && (
          <div className="bg-white rounded-xl border border-blue-200 px-3.5 py-2.5 shadow-micro flex items-start justify-between gap-2">
            <div className="flex items-start gap-2 text-xs text-zinc-700">
              <CheckCircle2 className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
              <span>{coachBanner}</span>
            </div>
            <button
              type="button"
              onClick={() => setCoachBanner(null)}
              className="text-[11px] font-mono text-zinc-400 hover:text-zinc-700"
            >
              ✕
            </button>
          </div>
        )}

        {/* Rule 2: 10:00 Next-Morning Diagnostic Check Banner (if yesterday unlogged) */}
        {summary?.missed_yesterday_unlogged && activeTab === 'TODAY' && (
          <div className="bg-[#FFFBEB] rounded-xl border border-amber-300 p-3.5 shadow-micro space-y-2.5">
            <div className="flex items-center gap-1.5 text-amber-800 text-xs font-semibold">
              <ShieldAlert className="w-4 h-4 text-amber-600" />
              <span>10:00 Diagnostic Check — No Nagging Repeats</span>
            </div>
            <p className="text-xs text-zinc-700">
              Missed yesterday&apos;s pulse. Crazy day, or did we hit friction on the plan?
            </p>
            <div className="flex flex-wrap gap-1.5">
              <button
                type="button"
                onClick={() => {
                  triggerHaptic('medium');
                  diagnosticMutation.mutate('LOG_YESTERDAY_ALL');
                }}
                className="px-2.5 py-1.5 rounded-lg bg-white border border-amber-300 text-zinc-900 text-[11px] font-medium hover:bg-amber-50 transition"
              >
                Log Yesterday All ✅
              </button>
              <button
                type="button"
                onClick={() => {
                  triggerHaptic('medium');
                  diagnosticMutation.mutate('CRAZY_DAY_RESUME');
                }}
                className="px-2.5 py-1.5 rounded-lg bg-white border border-amber-300 text-zinc-900 text-[11px] font-medium hover:bg-amber-50 transition"
              >
                Crazy Day - Resume Today
              </button>
              <button
                type="button"
                onClick={() => {
                  triggerHaptic('medium');
                  diagnosticMutation.mutate('ADJUST_WEEKLY_LOAD');
                }}
                className="px-2.5 py-1.5 rounded-lg bg-white border border-amber-300 text-zinc-900 text-[11px] font-medium hover:bg-amber-50 transition"
              >
                Adjust Weekly Load
              </button>
            </div>
          </div>
        )}

        {/* TAB 1: TODAY VIEW */}
        {activeTab === 'TODAY' && (
          <div className="space-y-2.5">
            <div className="flex items-center justify-between px-0.5">
              <span className="text-[11px] font-mono uppercase tracking-wider text-zinc-400">
                Today&apos;s Controllable Lead Measures ({ todayQuery.data?.date || 'Today' })
              </span>
              <span className="text-[11px] font-mono text-zinc-400">
                1-Tap Logging
              </span>
            </div>

            {todayQuery.isLoading ? (
              <div className="bg-white rounded-xl border border-zinc-200 p-6 text-center text-xs text-zinc-500">
                Loading today&apos;s cadence telemetry...
              </div>
            ) : (
              goals.map((goal) => (
                <TodayCheckInCard
                  key={goal.id}
                  goal={goal}
                  isUpdating={toggleMutation.isPending || bargainMutation.isPending}
                  onToggleStatus={(goalId, result) =>
                    toggleMutation.mutate({ goalId, result })
                  }
                  onResolveBargain={(goalId, action) =>
                    bargainMutation.mutate({ goalId, action })
                  }
                />
              ))
            )}

            {/* Non-Annoying Rigor Legend Card */}
            <div className="bg-white rounded-xl border border-zinc-200 p-3.5 shadow-micro flex items-start gap-2.5">
              <Info className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
              <div className="text-[11px] text-zinc-600 leading-relaxed">
                <strong className="text-zinc-900">Non-Annoying Rigor Engine:</strong>{' '}
                Habits at <span className="font-mono text-zinc-800">5d+ streak</span> earn{' '}
                <span className="text-blue-600 font-medium">Earned Silence</span> (morning
                reminders suppressed). Habits with{' '}
                <span className="font-mono text-rose-600">2x consecutive misses</span>{' '}
                trigger <span className="text-rose-600 font-medium">The Coach&apos;s Bargain</span>.
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: CASCADE TREE VIEW */}
        {activeTab === 'CASCADE' && (
          <GoalCascadeTree
            tree={treeQuery.data || []}
            horizonFilter={horizonFilter}
            onUpdateNode={(goalId, payload) =>
              updateNodeMutation.mutate({ goalId, payload })
            }
            onAddChildNode={(payload) => createNodeMutation.mutate(payload)}
          />
        )}

        {/* TAB 3: SCORECARD & HORIZON AUDIT VIEW */}
        {activeTab === 'SCORECARD' && (
          <ScorecardView scorecard={scorecardQuery.data} />
        )}
      </main>

      {/* AI Cascade Onboarding Modal */}
      <OnboardingModal
        isOpen={onboardingOpen}
        onClose={() => setOnboardingOpen(false)}
        onLockedIn={() => {
          setCoachBanner('New AI Goal Cascade locked in across all 4 horizons.');
          refreshAll();
        }}
      />
    </div>
  );
};

export default App;

