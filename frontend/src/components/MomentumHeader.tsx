import React from 'react';
import { Activity, Flame, Sparkles, VolumeX } from 'lucide-react';
import { MomentumSummary } from '../lib/api';
import { triggerHaptic } from '../lib/telegram';

interface MomentumHeaderProps {
  summary?: MomentumSummary;
  onOpenOnboarding: () => void;
}

export const MomentumHeader: React.FC<MomentumHeaderProps> = ({
  summary,
  onOpenOnboarding,
}) => {
  const cadenceScore = summary?.cadence_score ?? 88;
  const activeStreak = summary?.active_streak_days ?? 7;
  const completedToday = summary?.completed_today ?? 2;
  const totalToday = summary?.total_today ?? 5;
  const earnedSilenceCount = summary?.earned_silence_count ?? 3;

  const isOnTrack = cadenceScore >= 75;
  const isSlipping = cadenceScore >= 50 && cadenceScore < 75;

  return (
    <header className="sticky top-0 z-20 bg-[#FAFAFA]/95 backdrop-blur-sm border-b border-zinc-200 px-4 pt-3 pb-3">
      <div className="max-w-xl mx-auto flex flex-col gap-2.5">
        {/* Top Row: Brand Title + Rhythm Pill + AI Cascade CTA */}
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-blue-600 text-white flex items-center justify-center font-mono text-xs font-semibold tracking-tight shadow-micro">
              C
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <h1 className="text-sm font-semibold tracking-tight text-zinc-900">
                  Cadence
                </h1>
                <span className="text-[11px] font-mono text-zinc-400">
                  • {summary?.timezone?.split('/')[1]?.replace('_', ' ') || 'KL'}
                </span>
              </div>
              <p className="text-[11px] text-zinc-600 leading-none">
                Multi-Horizon Performance Studio
              </p>
            </div>
          </div>

          <div className="flex items-center gap-1.5">
            {/* Rhythm Score Pill */}
            <div
              className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-xs font-mono font-medium ${
                isOnTrack
                  ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
                  : isSlipping
                  ? 'bg-amber-50 border-amber-200 text-amber-700'
                  : 'bg-rose-50 border-rose-200 text-rose-700'
              }`}
            >
              <Activity className="w-3.5 h-3.5" />
              <span>{cadenceScore}% On Cadence</span>
            </div>

            {/* Streak Pill */}
            <div className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-zinc-100 border border-zinc-200 text-zinc-900 text-xs font-mono font-medium">
              <Flame className="w-3.5 h-3.5 text-amber-500" />
              <span>{activeStreak}d</span>
            </div>
          </div>
        </div>

        {/* Sub-bar: Today's Lead Measure Progress + Earned Silence Badge + Cascade AI Button */}
        <div className="flex items-center justify-between text-xs pt-0.5">
          <div className="flex items-center gap-3 text-zinc-600">
            <span className="font-mono text-[11px] text-zinc-700">
              Today:{' '}
              <strong className="text-zinc-900">
                {completedToday}/{totalToday}
              </strong>{' '}
              Lead Measures
            </span>
            {earnedSilenceCount > 0 && (
              <span
                title="Rule 1: Morning reminders suppressed for habits with 5d+ streak"
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-zinc-100 text-zinc-600 font-mono text-[11px] border border-zinc-200/80"
              >
                <VolumeX className="w-3 h-3 text-blue-600" />
                {earnedSilenceCount} Earned Silence
              </span>
            )}
          </div>

          <button
            type="button"
            onClick={() => {
              triggerHaptic('light');
              onOpenOnboarding();
            }}
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-blue-600 hover:bg-blue-700 active:scale-[0.99] text-white text-[11px] font-medium transition shadow-micro"
          >
            <Sparkles className="w-3 h-3" />
            <span>AI Cascade</span>
          </button>
        </div>
      </div>
    </header>
  );
};

