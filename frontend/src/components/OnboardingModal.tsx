import React, { useState } from 'react';
import { Check, RotateCcw, Sparkles, TrendingDown, X } from 'lucide-react';
import { CascadeProposal, cadenceApi } from '../lib/api';
import { triggerHaptic } from '../lib/telegram';

interface OnboardingModalProps {
  isOpen: boolean;
  onClose: () => void;
  onLockedIn: (message?: string) => void;
}

export const OnboardingModal: React.FC<OnboardingModalProps> = ({
  isOpen,
  onClose,
  onLockedIn,
}) => {
  const [brainDump, setBrainDump] = useState('');
  const [proposal, setProposal] = useState<CascadeProposal | null>(null);
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleDecompose = async () => {
    if (!brainDump.trim()) return;
    triggerHaptic('light');
    setLoading(true);
    try {
      const res = await cadenceApi.decomposeOnboarding(brainDump, false);
      setProposal(res);
    } finally {
      setLoading(false);
    }
  };

  const handleResetAll = async () => {
    triggerHaptic('heavy');
    setLoading(true);
    try {
      const res = await cadenceApi.resetCadence();
      setProposal(null);
      setBrainDump('');
      onLockedIn(res.message);
    } finally {
      setLoading(false);
    }
  };

  const handleMakeLessAggressive = async () => {
    if (!proposal) return;
    triggerHaptic('medium');
    setLoading(true);
    try {
      const scaled = await cadenceApi.scaleDownProposal(proposal);
      setProposal(scaled);
    } finally {
      setLoading(false);
    }
  };

  const handleLockIn = async () => {
    if (!proposal) return;
    triggerHaptic('heavy');
    setLoading(true);
    try {
      await cadenceApi.lockInProposal(proposal);
      onLockedIn('New AI Goal Cascade locked in across all 4 horizons.');
      onClose();
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-zinc-900/40 backdrop-blur-[2px] flex items-end sm:items-center justify-center p-2 sm:p-4">
      <div className="bg-white w-full max-w-lg rounded-2xl border border-zinc-200 shadow-xl p-4 sm:p-5 max-h-[90vh] overflow-y-auto space-y-4">
        <div className="flex items-center justify-between border-b border-zinc-100 pb-3">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-blue-600 text-white flex items-center justify-center">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-zinc-900">
                &ldquo;The Cascade&rdquo; AI Onboarding
              </h2>
              <p className="text-[11px] text-zinc-500">
                OpenRouter Structured Decomposition: Annual Lag → Daily Lead Measures
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-lg text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Input Box */}
        <div className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <label className="block text-xs font-medium text-zinc-700">
              Describe your Annual Goals (or send a voice note in Telegram chat):
            </label>
            <button
              type="button"
              disabled={loading}
              onClick={handleResetAll}
              className="inline-flex items-center gap-1 px-2 py-1 rounded-lg border border-rose-200 bg-rose-50 hover:bg-rose-100 text-rose-700 text-[11px] font-medium transition shrink-0"
              title="Wipe all existing template goals and check-in history"
            >
              <RotateCcw className="w-3 h-3" />
              <span>Reset All</span>
            </button>
          </div>
          <textarea
            rows={3}
            value={brainDump}
            onChange={(e) => setBrainDump(e.target.value)}
            className="w-full rounded-xl border border-zinc-200 bg-[#FAFAFA] p-3 text-xs text-zinc-900 focus:outline-none focus:ring-2 focus:ring-blue-600"
            placeholder="e.g. This year I want to ship v2 of my library, run a sub-20m 5K while lifting 3x/week, and read 24 books..."
          />
          <button
            type="button"
            disabled={loading || !brainDump.trim()}
            onClick={handleDecompose}
            className="w-full py-2 px-4 rounded-xl bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white text-xs font-medium transition shadow-micro"
          >
            {loading ? 'Decomposing Goal Hierarchy...' : 'Generate Multi-Horizon Cascade'}
          </button>
        </div>

        {/* Preview & Calibration */}
        {proposal && (
          <div className="space-y-3 pt-2 border-t border-zinc-200">
            <div className="p-3 rounded-xl bg-zinc-100 border border-zinc-200 text-xs text-zinc-700 leading-relaxed">
              <strong className="text-zinc-900">Coach Note:</strong> {proposal.coach_summary}
            </div>

            <div className="space-y-2.5 max-h-60 overflow-y-auto pr-1">
              {proposal.annual_goals.map((ag, idx) => (
                <div
                  key={idx}
                  className="p-3 rounded-xl bg-[#FAFAFA] border border-zinc-200 space-y-1.5 text-xs"
                >
                  <div className="font-semibold text-zinc-900">
                    🏔️ [{ag.category}] {ag.title}
                  </div>
                  {ag.monthly_targets.map((mg, mIdx) => (
                    <div key={mIdx} className="pl-3 border-l border-zinc-300 space-y-1">
                      <div className="text-zinc-700 font-medium">🗓️ {mg.title}</div>
                      {mg.weekly_milestones.map((wg, wIdx) => (
                        <div key={wIdx} className="pl-3 space-y-1">
                          <div className="text-zinc-600 text-[11px]">
                            📈 {wg.title} ({wg.target_metric})
                          </div>
                          {wg.daily_actions.map((dg, dIdx) => (
                            <div
                              key={dIdx}
                              className="pl-3 text-[11px] font-mono text-blue-700"
                            >
                              • ⚡ {dg.title} [{dg.frequency_per_week}x/wk]
                            </div>
                          ))}
                        </div>
                      ))}
                    </div>
                  ))}
                </div>
              ))}
            </div>

            {/* Calibration Buttons matching Spec 3.1 */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1">
              <button
                type="button"
                disabled={loading}
                onClick={handleMakeLessAggressive}
                className="flex items-center justify-center gap-1.5 py-2 px-3 rounded-xl bg-zinc-100 hover:bg-zinc-200 text-zinc-800 border border-zinc-200 text-xs font-medium transition"
              >
                <TrendingDown className="w-3.5 h-3.5 text-amber-600" />
                <span>📉 Make Less Aggressive</span>
              </button>
              <button
                type="button"
                disabled={loading}
                onClick={handleLockIn}
                className="flex items-center justify-center gap-1.5 py-2 px-3 rounded-xl bg-[#10B981] hover:bg-emerald-600 text-white text-xs font-semibold transition shadow-micro"
              >
                <Check className="w-3.5 h-3.5" />
                <span>✅ Lock In Cadence</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

