import React, { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CheckCircle2, Info, KeyRound, Lock, ShieldAlert } from 'lucide-react';
import {
  CheckInResult,
  GoalStatus,
  HorizonLevel,
  UnauthorizedError,
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
  const [pinInput, setPinInput] = useState('');
  const [pinError, setPinError] = useState<string | null>(null);
  const [unlocking, setUnlocking] = useState(false);

  useEffect(() => {
    initTelegramLightTheme();
  }, []);

  const todayQuery = useQuery({
    queryKey: ['todayView'],
    queryFn: cadenceApi.getTodayView,
    retry: (failureCount, error) => {
      if (error instanceof UnauthorizedError) return false;
      return failureCount < 1;
    },
  });

  const isLocked = todayQuery.error instanceof UnauthorizedError;

  const treeQuery = useQuery({
    queryKey: ['goalsTree'],
    queryFn: cadenceApi.getGoalsTree,
    enabled: !isLocked && todayQuery.isSuccess,
  });

  const scorecardQuery = useQuery({
    queryKey: ['scorecard'],
    queryFn: cadenceApi.getScorecard,
    enabled: !isLocked && todayQuery.isSuccess,
  });

  const refreshAll = () => {
    queryClient.invalidateQueries({ queryKey: ['todayView'] });
    queryClient.invalidateQueries({ queryKey: ['goalsTree'] });
    queryClient.invalidateQueries({ queryKey: ['scorecard'] });
  };

  const handleUnlockSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pinInput.trim()) return;
    setUnlocking(true);
    setPinError(null);
    try {
      await cadenceApi.unlockWithPassphrase(pinInput.trim());
      triggerHaptic('medium');
      setPinInput('');
      refreshAll();
    } catch {
      triggerHaptic('heavy');
      setPinError('Invalid passphrase or PIN. Please try again.');
    } finally {
      setUnlocking(false);
    }
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

  // Clean Light-Theme Passphrase / PIN Gate Screen
  if (isLocked) {
    return (
      <div className="min-h-screen bg-[#FAFAFA] text-[#18181B] flex items-center justify-center p-4">
        <form
          onSubmit={handleUnlockSubmit}
          className="w-full max-w-sm bg-white rounded-2xl border border-zinc-200 shadow-micro p-6 space-y-4"
        >
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-blue-600 text-white flex items-center justify-center shadow-micro">
              <Lock className="w-4 h-4" />
            </div>
            <div>
              <h1 className="text-sm font-semibold text-zinc-900">
                Cadence Studio Locked
              </h1>
              <p className="text-xs text-zinc-500">
                Enter your access passphrase or PIN
              </p>
            </div>
          </div>

          <div className="space-y-1.5">
            <div className="relative">
              <KeyRound className="w-4 h-4 text-zinc-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="password"
                autoFocus
                required
                value={pinInput}
                onChange={(e) => setPinInput(e.target.value)}
                placeholder="Passphrase / PIN..."
                className="w-full pl-9 pr-3 py-2 text-xs font-mono rounded-xl border border-zinc-200 bg-[#FAFAFA] text-zinc-900 focus:outline-none focus:ring-2 focus:ring-blue-600"
              />
            </div>
            {pinError && (
              <p className="text-[11px] text-rose-600 font-medium">{pinError}</p>
            )}
          </div>

          <button
            type="submit"
            disabled={unlocking}
            className="w-full py-2 px-4 rounded-xl bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white text-xs font-semibold transition shadow-micro"
          >
            {unlocking ? 'Verifying...' : 'Unlock Cadence'}
          </button>
        </form>
      </div>
    );
  }

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
                Today&apos;s Controllable Lead Measures ({todayQuery.data?.date || 'Today'})
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
