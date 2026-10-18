import React from 'react';
import { Compass, Layers, MessageSquareCode } from 'lucide-react';
import { ScorecardResponse } from '../lib/api';

interface ScorecardViewProps {
  scorecard?: ScorecardResponse;
}

export const ScorecardView: React.FC<ScorecardViewProps> = ({ scorecard }) => {
  if (!scorecard) {
    return (
      <div className="bg-white rounded-xl border border-zinc-200 p-6 text-center text-xs text-zinc-500">
        Loading 7-Day Telemetry & Horizon Audit...
      </div>
    );
  }

  return (
    <div className="space-y-3.5">
      {/* 1. Weekly Sunday Strategy — 7-Day Rhythm Bars */}
      <div className="bg-white rounded-xl border border-zinc-200 p-4 shadow-micro">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h2 className="text-xs font-semibold text-zinc-900 uppercase tracking-wider font-mono">
              7-Day Execution Telemetry
            </h2>
            <p className="text-[11px] text-zinc-500">
              Sunday Strategy Snapshot • Daily Lead Measure Completion
            </p>
          </div>
          <span className="px-2.5 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-700 font-mono text-xs font-semibold">
            {scorecard.summary.cadence_score}% Rhythm
          </span>
        </div>

        <div className="grid grid-cols-7 gap-2 pt-2">
          {scorecard.weekly_days.map((day) => {
            const barColor =
              day.completion_pct >= 80
                ? 'bg-[#10B981]'
                : day.completion_pct >= 50
                ? 'bg-[#F59E0B]'
                : 'bg-[#F43F5E]';

            return (
              <div key={day.date} className="flex flex-col items-center gap-1.5">
                <div className="w-full h-24 rounded-lg bg-zinc-100 border border-zinc-200/60 flex items-end p-1 overflow-hidden">
                  <div
                    className={`w-full rounded transition-all duration-300 ${barColor}`}
                    style={{ height: `${Math.max(10, day.completion_pct)}%` }}
                  />
                </div>
                <span className="font-mono text-[10px] font-medium text-zinc-700">
                  {day.label}
                </span>
                <span className="font-mono text-[10px] text-zinc-400">
                  {day.completion_pct}%
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* 2. Monthly Horizon Audit: Weekly Execution vs Monthly Milestone */}
      <div className="bg-white rounded-xl border border-zinc-200 p-4 shadow-micro">
        <div className="flex items-center gap-2 mb-3">
          <Layers className="w-4 h-4 text-blue-600" />
          <div>
            <h2 className="text-xs font-semibold text-zinc-900 uppercase tracking-wider font-mono">
              Monthly Horizon Audit
            </h2>
            <p className="text-[11px] text-zinc-500">
              Evaluates whether Weekly Lead Execution is moving Monthly Lag Milestones
            </p>
          </div>
        </div>

        <div className="space-y-3">
          {scorecard.horizon_audit.map((item) => {
            const statusStyle =
              item.status_label === 'ON_TRACK'
                ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                : item.status_label === 'SLIPPING'
                ? 'bg-amber-50 text-amber-700 border-amber-200'
                : 'bg-rose-50 text-rose-700 border-rose-200';

            return (
              <div
                key={item.monthly_goal_id}
                className="p-3 rounded-lg bg-[#FAFAFA] border border-zinc-200/90 space-y-2"
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <span className="text-[10px] font-mono text-zinc-500 uppercase">
                      {item.category} • ↳ {item.annual_title}
                    </span>
                    <h3 className="text-xs font-semibold text-zinc-900">
                      {item.monthly_title}
                    </h3>
                  </div>
                  <span
                    className={`px-2 py-0.5 rounded-full border font-mono text-[10px] font-medium shrink-0 ${statusStyle}`}
                  >
                    {item.status_label.replace('_', ' ')}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-3 pt-1">
                  <div>
                    <div className="flex justify-between text-[11px] text-zinc-600 mb-1">
                      <span>Weekly Lead Exec</span>
                      <span className="font-mono font-semibold text-zinc-900">
                        {item.weekly_execution_pct}%
                      </span>
                    </div>
                    <div className="h-1.5 rounded-full bg-zinc-200 overflow-hidden">
                      <div
                        className="h-full bg-blue-600 rounded-full"
                        style={{ width: `${item.weekly_execution_pct}%` }}
                      />
                    </div>
                  </div>

                  <div>
                    <div className="flex justify-between text-[11px] text-zinc-600 mb-1">
                      <span>Monthly Lag Target</span>
                      <span className="font-mono font-semibold text-zinc-900">
                        {item.monthly_milestone_pct}%
                      </span>
                    </div>
                    <div className="h-1.5 rounded-full bg-zinc-200 overflow-hidden">
                      <div
                        className="h-full bg-emerald-500 rounded-full"
                        style={{ width: `${item.monthly_milestone_pct}%` }}
                      />
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 3. Sunday Strategy Diagnostic Prompt */}
      <div className="bg-white rounded-xl border border-blue-200 p-4 shadow-micro">
        <div className="flex items-center gap-2 text-blue-600 text-xs font-semibold mb-1.5">
          <Compass className="w-4 h-4" />
          <span>Coach Diagnostic Question (Sunday Strategy)</span>
        </div>
        <p className="text-xs text-zinc-700 leading-relaxed italic">
          &ldquo;{scorecard.diagnostic_question}&rdquo;
        </p>
        <div className="mt-2.5 flex items-center gap-1.5 text-[11px] text-zinc-400">
          <MessageSquareCode className="w-3.5 h-3.5" />
          <span>Reply via voice note or text in the Cadence Telegram chat to recalibrate.</span>
        </div>
      </div>
    </div>
  );
};

