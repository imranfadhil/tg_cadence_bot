import React from 'react';
import { CalendarCheck2, GitBranch, BarChart3 } from 'lucide-react';
import { HorizonLevel } from '../lib/api';
import { triggerHaptic } from '../lib/telegram';

export type MainViewTab = 'TODAY' | 'CASCADE' | 'SCORECARD';

interface HorizonTabsProps {
  activeTab: MainViewTab;
  onSelectTab: (tab: MainViewTab) => void;
  horizonFilter: HorizonLevel | 'ALL';
  onSelectHorizonFilter: (horizon: HorizonLevel | 'ALL') => void;
  bargainCount?: number;
}

export const HorizonTabs: React.FC<HorizonTabsProps> = ({
  activeTab,
  onSelectTab,
  horizonFilter,
  onSelectHorizonFilter,
  bargainCount = 0,
}) => {
  const tabs: { id: MainViewTab; label: string; icon: React.ReactNode; badge?: number }[] = [
    {
      id: 'TODAY',
      label: 'Today',
      icon: <CalendarCheck2 className="w-3.5 h-3.5" />,
      badge: bargainCount > 0 ? bargainCount : undefined,
    },
    {
      id: 'CASCADE',
      label: 'Cascade Tree',
      icon: <GitBranch className="w-3.5 h-3.5" />,
    },
    {
      id: 'SCORECARD',
      label: 'Scorecard',
      icon: <BarChart3 className="w-3.5 h-3.5" />,
    },
  ];

  const horizons: { id: HorizonLevel | 'ALL'; label: string }[] = [
    { id: 'ALL', label: 'All Horizons' },
    { id: 'ANNUAL', label: 'Annual' },
    { id: 'MONTHLY', label: 'Monthly' },
    { id: 'WEEKLY', label: 'Weekly' },
    { id: 'DAILY', label: 'Daily' },
  ];

  return (
    <div className="max-w-xl mx-auto px-4 pt-3 pb-1 flex flex-col gap-2.5">
      {/* Primary Segmented Control: Today | Cascade Tree | Scorecard */}
      <div className="grid grid-cols-3 gap-1 p-1 rounded-xl bg-zinc-100 border border-zinc-200">
        {tabs.map((tab) => {
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => {
                triggerHaptic('light');
                onSelectTab(tab.id);
              }}
              className={`flex items-center justify-center gap-1.5 py-1.5 px-2.5 rounded-lg text-xs font-medium transition-all ${
                isActive
                  ? 'bg-white text-zinc-900 shadow-micro border border-zinc-200/80'
                  : 'text-zinc-600 hover:text-zinc-900'
              }`}
            >
              <span className={isActive ? 'text-blue-600' : 'text-zinc-500'}>
                {tab.icon}
              </span>
              <span>{tab.label}</span>
              {tab.badge !== undefined && (
                <span className="ml-0.5 px-1.5 py-0.2 rounded-full bg-rose-50 text-rose-600 border border-rose-200 font-mono text-[10px]">
                  {tab.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Secondary Horizon Switcher when viewing the Cascade Tree */}
      {activeTab === 'CASCADE' && (
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 no-scrollbar">
          {horizons.map((h) => {
            const selected = horizonFilter === h.id;
            return (
              <button
                key={h.id}
                type="button"
                onClick={() => {
                  triggerHaptic('light');
                  onSelectHorizonFilter(h.id);
                }}
                className={`px-2.5 py-1 rounded-full text-[11px] font-mono whitespace-nowrap transition border ${
                  selected
                    ? 'bg-blue-600 text-white border-blue-600'
                    : 'bg-white text-zinc-600 border-zinc-200 hover:border-zinc-300'
                }`}
              >
                {h.label}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
};

