import React, { useState } from 'react';
import {
  ChevronDown,
  ChevronRight,
  Edit3,
  Flame,
  Plus,
  Check,
  X,
  VolumeX,
} from 'lucide-react';
import { GoalStatus, GoalTreeNode, HorizonLevel } from '../lib/api';
import { triggerHaptic } from '../lib/telegram';

interface GoalCascadeTreeProps {
  tree: GoalTreeNode[];
  horizonFilter: HorizonLevel | 'ALL';
  onUpdateNode: (
    goalId: string,
    payload: {
      title: string;
      horizon: HorizonLevel;
      target_value: number;
      status: GoalStatus;
      category?: string | null;
    }
  ) => void;
  onAddChildNode: (payload: {
    title: string;
    horizon: HorizonLevel;
    parent_id?: string | null;
    category?: string | null;
    target_value: number;
  }) => void;
}

const HORIZON_META: Record<
  HorizonLevel,
  { badge: string; label: string; nextChild?: HorizonLevel }
> = {
  ANNUAL: {
    label: 'ANNUAL LAG',
    badge: 'bg-blue-50 text-blue-700 border-blue-200',
    nextChild: 'MONTHLY',
  },
  MONTHLY: {
    label: 'MONTHLY',
    badge: 'bg-zinc-100 text-zinc-700 border-zinc-200',
    nextChild: 'WEEKLY',
  },
  WEEKLY: {
    label: 'WEEKLY',
    badge: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    nextChild: 'DAILY',
  },
  DAILY: {
    label: 'DAILY LEAD',
    badge: 'bg-amber-50 text-amber-700 border-amber-200',
  },
};

function collectFilteredNodes(
  nodes: GoalTreeNode[],
  targetHorizon: HorizonLevel
): GoalTreeNode[] {
  const result: GoalTreeNode[] = [];
  const walk = (list: GoalTreeNode[]) => {
    for (const item of list) {
      if (item.horizon === targetHorizon) {
        result.push(item);
      }
      if (item.children?.length) {
        walk(item.children);
      }
    }
  };
  walk(nodes);
  return result;
}

export const GoalCascadeTree: React.FC<GoalCascadeTreeProps> = ({
  tree,
  horizonFilter,
  onUpdateNode,
  onAddChildNode,
}) => {
  const [collapsedIds, setCollapsedIds] = useState<Record<string, boolean>>({});
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [editTarget, setEditTarget] = useState('5');
  const [addingParent, setAddingParent] = useState<{
    parentId: string | null;
    horizon: HorizonLevel;
    category?: string | null;
  } | null>(null);
  const [newNodeTitle, setNewNodeTitle] = useState('');
  const [newNodeTarget, setNewNodeTarget] = useState('5');

  const toggleExpand = (id: string) => {
    triggerHaptic('light');
    setCollapsedIds((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const startEdit = (node: GoalTreeNode) => {
    triggerHaptic('light');
    setEditingId(node.id);
    setEditTitle(node.title);
    setEditTarget(String(node.target_value));
  };

  const saveEdit = (node: GoalTreeNode) => {
    triggerHaptic('medium');
    onUpdateNode(node.id, {
      title: editTitle.trim() || node.title,
      horizon: node.horizon,
      target_value: Math.max(1, parseFloat(editTarget) || node.target_value),
      status: node.status,
      category: node.category,
    });
    setEditingId(null);
  };

  const handleCreateChild = (e: React.FormEvent) => {
    e.preventDefault();
    if (!addingParent || !newNodeTitle.trim()) return;
    triggerHaptic('medium');
    onAddChildNode({
      title: newNodeTitle.trim(),
      horizon: addingParent.horizon,
      parent_id: addingParent.parentId,
      category: addingParent.category || 'Engineering',
      target_value: Math.max(1, parseFloat(newNodeTarget) || 5),
    });
    setAddingParent(null);
    setNewNodeTitle('');
  };

  const renderNode = (node: GoalTreeNode, depth = 0): React.ReactNode => {
    const hasChildren = node.children && node.children.length > 0;
    const isCollapsed = !!collapsedIds[node.id];
    const meta = HORIZON_META[node.horizon];
    const isEditing = editingId === node.id;

    const barColor =
      node.progress_pct >= 75
        ? 'bg-[#10B981]'
        : node.progress_pct >= 50
        ? 'bg-[#F59E0B]'
        : 'bg-[#2563EB]';

    return (
      <div key={node.id} className={depth > 0 ? 'mt-2 pl-3.5 border-l border-zinc-200' : 'mt-3'}>
        <div className="bg-white rounded-xl border border-zinc-200 p-3 shadow-micro hover:border-zinc-300/90 transition">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-start gap-2 min-w-0 flex-1">
              {hasChildren ? (
                <button
                  type="button"
                  onClick={() => toggleExpand(node.id)}
                  className="mt-0.5 p-0.5 rounded hover:bg-zinc-100 text-zinc-500"
                >
                  {isCollapsed ? (
                    <ChevronRight className="w-4 h-4" />
                  ) : (
                    <ChevronDown className="w-4 h-4" />
                  )}
                </button>
              ) : (
                <span className="w-5 h-5 inline-flex items-center justify-center text-zinc-300 font-mono text-xs">
                  •
                </span>
              )}

              <div className="min-w-0 flex-1">
                {/* Badges Row */}
                <div className="flex flex-wrap items-center gap-1.5 mb-1">
                  <span
                    className={`px-1.5 py-0.5 rounded border font-mono text-[10px] font-medium ${meta.badge}`}
                  >
                    {meta.label}
                  </span>
                  {node.category && depth === 0 && (
                    <span className="px-1.5 py-0.5 rounded bg-zinc-100 text-zinc-600 font-mono text-[10px] border border-zinc-200">
                      {node.category}
                    </span>
                  )}
                  {node.earned_silence && (
                    <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-blue-50 text-blue-600 border border-blue-200 font-mono text-[10px]">
                      <VolumeX className="w-2.5 h-2.5" />
                      Silence
                    </span>
                  )}
                  {node.streak_count > 0 && (
                    <span className="inline-flex items-center gap-0.5 font-mono text-[10px] text-zinc-500">
                      <Flame className="w-3 h-3 text-amber-500" />
                      {node.streak_count}d
                    </span>
                  )}
                </div>

                {/* Title or Inline Studio Editor */}
                {isEditing ? (
                  <div className="flex flex-col sm:flex-row gap-1.5 mt-1">
                    <input
                      type="text"
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      className="flex-1 px-2.5 py-1 text-xs rounded-lg border border-zinc-300 bg-[#FAFAFA] text-zinc-900 focus:outline-none focus:ring-2 focus:ring-blue-600"
                    />
                    <div className="flex items-center gap-1">
                      <input
                        type="number"
                        step="0.5"
                        value={editTarget}
                        onChange={(e) => setEditTarget(e.target.value)}
                        className="w-16 px-2 py-1 text-xs font-mono rounded-lg border border-zinc-300 bg-[#FAFAFA] text-zinc-900"
                        title="Target value"
                      />
                      <button
                        type="button"
                        onClick={() => saveEdit(node)}
                        className="p-1.5 rounded-lg bg-blue-600 text-white hover:bg-blue-700"
                      >
                        <Check className="w-3.5 h-3.5" />
                      </button>
                      <button
                        type="button"
                        onClick={() => setEditingId(null)}
                        className="p-1.5 rounded-lg bg-zinc-100 text-zinc-600 hover:bg-zinc-200"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                ) : (
                  <p className="text-xs sm:text-sm font-medium text-zinc-900 leading-snug">
                    {node.title}
                  </p>
                )}
              </div>
            </div>

            {/* Right Metrics & Studio Actions */}
            {!isEditing && (
              <div className="flex items-center gap-1.5 shrink-0">
                <span className="font-mono text-xs font-semibold text-zinc-800">
                  {node.progress_pct}%
                </span>
                <button
                  type="button"
                  onClick={() => startEdit(node)}
                  title="Edit in Studio"
                  className="p-1 rounded-md text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100"
                >
                  <Edit3 className="w-3.5 h-3.5" />
                </button>
                {meta.nextChild && (
                  <button
                    type="button"
                    onClick={() => {
                      triggerHaptic('light');
                      setAddingParent({
                        parentId: node.id,
                        horizon: meta.nextChild!,
                        category: node.category,
                      });
                    }}
                    title={`Add ${meta.nextChild} child goal`}
                    className="p-1 rounded-md text-zinc-400 hover:text-blue-600 hover:bg-blue-50"
                  >
                    <Plus className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            )}
          </div>

          {/* Thin Editorial Progress Bar */}
          <div className="mt-2.5 flex items-center gap-2">
            <div className="flex-1 h-1.5 rounded-full bg-zinc-100 overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-300 ${barColor}`}
                style={{ width: `${Math.min(100, Math.max(4, node.progress_pct))}%` }}
              />
            </div>
            <span className="font-mono text-[10px] text-zinc-400">
              {node.current_value}/{node.target_value}
            </span>
          </div>
        </div>

        {/* Recursive Children */}
        {hasChildren && !isCollapsed && (
          <div className="space-y-1.5">
            {node.children.map((child) => renderNode(child, depth + 1))}
          </div>
        )}
      </div>
    );
  };

  const displayNodes =
    horizonFilter === 'ALL'
      ? tree
      : collectFilteredNodes(tree, horizonFilter).map((n) => ({ ...n, children: [] }));

  return (
    <div className="space-y-3">
      {/* Top Studio Header */}
      <div className="flex items-center justify-between bg-white rounded-xl border border-zinc-200 px-3.5 py-2.5 shadow-micro">
        <div>
          <h2 className="text-xs font-semibold text-zinc-900">
            Cascading Goal Architecture
          </h2>
          <p className="text-[11px] text-zinc-500">
            Lag Measures (Annual → Monthly) linked to Daily controllable Lead Measures
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            triggerHaptic('light');
            setAddingParent({ parentId: null, horizon: 'ANNUAL', category: 'Engineering' });
          }}
          className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-zinc-100 hover:bg-zinc-200 text-zinc-800 text-xs font-medium border border-zinc-200 transition"
        >
          <Plus className="w-3.5 h-3.5 text-blue-600" />
          <span>New Annual Goal</span>
        </button>
      </div>

      {/* Add Node Inline Drawer */}
      {addingParent && (
        <form
          onSubmit={handleCreateChild}
          className="bg-white rounded-xl border border-blue-300 p-3.5 shadow-micro space-y-2.5"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-blue-600 font-mono">
              + ADD {addingParent.horizon} NODE
            </span>
            <button
              type="button"
              onClick={() => setAddingParent(null)}
              className="text-zinc-400 hover:text-zinc-600"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
          <div className="flex flex-col sm:flex-row gap-2">
            <input
              type="text"
              required
              placeholder={`Enter ${addingParent.horizon.toLowerCase()} goal title...`}
              value={newNodeTitle}
              onChange={(e) => setNewNodeTitle(e.target.value)}
              className="flex-1 px-3 py-1.5 text-xs rounded-lg border border-zinc-200 bg-[#FAFAFA] text-zinc-900 focus:outline-none focus:ring-2 focus:ring-blue-600"
            />
            <input
              type="number"
              step="1"
              value={newNodeTarget}
              onChange={(e) => setNewNodeTarget(e.target.value)}
              className="w-24 px-2.5 py-1.5 text-xs font-mono rounded-lg border border-zinc-200 bg-[#FAFAFA] text-zinc-900"
              placeholder="Target"
            />
            <button
              type="submit"
              className="px-3.5 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium"
            >
              Save Node
            </button>
          </div>
        </form>
      )}

      {/* Cascade Tree List */}
      <div>{displayNodes.map((node) => renderNode(node, 0))}</div>
    </div>
  );
};

