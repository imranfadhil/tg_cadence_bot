import React from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Flame,
  Scale,
  VolumeX,
  XCircle,
} from 'lucide-react';
import { CheckInResult, TodayGoalCard } from '../lib/api';
import { triggerHaptic } from '../lib/telegram';

interface TodayCheckInCardProps {
  goal: TodayGoalCard;
  isUpdating?: boolean;
  onToggleStatus: (goalId: string, result: CheckInResult) => void;
  onResolveBargain: (
    goalId: string,
    action: 'MICRO_5M' | 'SCALE_BACK_25' | 'PAUSE_MONDAY'
  ) => void;
}

export const TodayCheckInCard: React.FC<TodayCheckInCardProps> = ({
  goal,
  isUpdating = false,
  onToggleStatus,
  onResolveBargain,
}) => {
  const isPaused = goal.status === 'PAUSED';

  const statusButtons: {
    result: CheckInResult;
    label: string;
    activeClass: string;
    icon: React.ReactNode;
  }[] = [
    {
      result: 'DONE',
      label: 'Done',
      activeClass:
        'bg-[#ECFDF5] border-[#10B981] text-[#065F46] ring-1 ring-[#10B981]/30',
      icon: <CheckCircle2 className="w-3.5 h-3.5 text-[#10B981]" />,
    },
    {
      result: 'PARTIAL',
      label: 'Partial',
      activeClass:
        'bg-[#FFFBEB] border-[#F59E0B] text-[#92400E] ring-1 ring-[#F59E0B]/30',
      icon: <Clock className="w-3.5 h-3.5 text-[#F59E0B]" />,
    },
    {
      result: 'MISSED',
      label: 'Missed',
      activeClass:
        'bg-[#FFF1F2] border-[#F43F5E] text-[#9F1239] ring-1 ring-[#F43F5E]/30',
      icon: <XCircle className="w-3.5 h-3.5 text-[#F43F5E]" />,
    },
  ];

  return (
    <div
      className={`bg-white rounded-xl border transition-all shadow-micro p-4 ${
        goal.needs_bargain
          ? 'border-rose-300'
          : goal.today_result === 'DONE'
          ? 'border-emerald-200/90'
          : 'border-zinc-200'
      } ${isPaused ? 'opacity-65' : ''}`}
    >
      {/* Top Meta Row: Category + Parent Breadcrumb + Streak / Earned Silence */}
      <div className="flex items-start justify-between gap-2 mb-1.5">
        <div className="flex flex-wrap items-center gap-1.5">
          {goal.category && (
            <span className="px-2 py-0.5 rounded bg-zinc-100 text-zinc-600 font-mono text-[10px] uppercase tracking-wider border border-zinc-200/70">
              {goal.category}
            </span>
          )}
          <span className="text-xs text-zinc-600 font-medium truncate max-w-[230px] sm:max-w-xs">
            {goal.breadcrumb}
          </span>
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          {goal.earned_silence && (
            <span
              title="Rule 1: Earned Silence — 5+ day streak suppresses morning reminders"
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-blue-50 text-blue-600 border border-blue-200 font-mono text-[10px]"
            >
              <VolumeX className="w-3 h-3" />
              5d+ Silence
            </span>
          )}
          <span
            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full font-mono text-[11px] border ${
              goal.streak_count >= 5
                ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                : 'bg-zinc-100 text-zinc-700 border-zinc-200'
            }`}
          >
            <Flame className="w-3 h-3 text-amber-500" />
            {goal.streak_count}d
          </span>
        </div>
      </div>

      {/* Main Daily Lead Measure Title */}
      <div className="flex items-baseline justify-between gap-2 mb-3">
        <h3
          className={`text-sm font-semibold leading-snug ${
            goal.today_result === 'DONE'
              ? 'text-zinc-900'
              : isPaused
              ? 'text-zinc-400 line-through'
              : 'text-zinc-900'
          }`}
        >
          {goal.title}
        </h3>
        <span className="font-mono text-[11px] text-zinc-400 shrink-0">
          {goal.current_value}/{goal.target_value} wk
        </span>
      </div>

      {/* 1-Tap Status Pills: Done | Partial | Missed */}
      <div className="grid grid-cols-3 gap-2">
        {statusButtons.map((btn) => {
          const isSelected = goal.today_result === btn.result;
          return (
            <button
              key={btn.result}
              type="button"
              disabled={isUpdating}
              onClick={() => {
                triggerHaptic('light');
                onToggleStatus(goal.id, btn.result);
              }}
              className={`flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg border text-xs font-medium transition active:scale-[0.98] ${
                isSelected
                  ? btn.activeClass
                  : 'bg-zinc-100/70 hover:bg-zinc-100 border-zinc-200 text-zinc-700'
              }`}
            >
              {btn.icon}
              <span>{btn.label}</span>
            </button>
          );
        })}
      </div>

      {/* Rule 3: The Coach's Bargain (2x Consecutive Misses Intervention) */}
      {goal.needs_bargain && (
        <div className="mt-3.5 pt-3 border-t border-rose-200/80 bg-[#FFF1F2]/60 -mx-4 -mb-4 px-4 pb-3.5 rounded-b-xl">
          <div className="flex items-center gap-1.5 text-rose-700 text-xs font-semibold mb-1">
            <Scale className="w-3.5 h-3.5 text-rose-500" />
            <span>The Coach&apos;s Bargain ({goal.consecutive_misses}x Missed)</span>
          </div>
          <p className="text-[11px] text-zinc-600 mb-2.5 leading-relaxed">
            Two consecutive misses indicate scope or schedule friction. Pick a tactical
            trade-off right now to protect your momentum:
          </p>
          <div className="flex flex-col sm:flex-row gap-1.5">
            <button
              type="button"
              onClick={() => {
                triggerHaptic('medium');
                onResolveBargain(goal.id, 'MICRO_5M');
              }}
              className="flex-1 py-1.5 px-2.5 rounded-lg bg-white hover:bg-zinc-50 text-zinc-900 border border-zinc-200 text-[11px] font-medium text-left sm:text-center shadow-micro transition"
            >
              ⚡ Do a 5-min micro-version now
            </button>
            <button
              type="button"
              onClick={() => {
                triggerHaptic('medium');
                onResolveBargain(goal.id, 'SCALE_BACK_25');
              }}
              className="flex-1 py-1.5 px-2.5 rounded-lg bg-white hover:bg-zinc-50 text-zinc-900 border border-zinc-200 text-[11px] font-medium text-left sm:text-center shadow-micro transition"
            >
              📉 Scale back weekly target by 25%
            </button>
            <button
              type="button"
              onClick={() => {
                triggerHaptic('medium');
                onResolveBargain(goal.id, 'PAUSE_MONDAY');
              }}
              className="flex-1 py-1.5 px-2.5 rounded-lg bg-white hover:bg-zinc-50 text-zinc-600 border border-zinc-200 text-[11px] font-medium text-left sm:text-center shadow-micro transition"
            >
              ⏸️ Pause habit until Monday
            </button>
          </div>
        </div>
      )}

      {goal.today_note && !goal.needs_bargain && (
        <div className="mt-2.5 pt-2 border-t border-zinc-100 flex items-center gap-1.5 text-[11px] text-zinc-500">
          <AlertTriangle className="w-3 h-3 text-zinc-400 shrink-0" />
          <span className="truncate">{goal.today_note}</span>
        </div>
      )}
    </div>
  );
};

