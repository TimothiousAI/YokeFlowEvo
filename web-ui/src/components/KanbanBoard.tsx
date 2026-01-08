/**
 * KanbanBoard - Kanban board for task management
 *
 * Features:
 * - Columns: Backlog | In Progress | Review | Done
 * - Task cards with status, epic, and worktree info
 * - Click to view task details
 * - Filter by epic
 * - Visual indicators for parallel execution
 *
 * Note: Drag-drop requires @dnd-kit (npm install @dnd-kit/core @dnd-kit/sortable)
 */

'use client';

import React, { useState, useMemo } from 'react';
import {
  CheckCircle,
  Circle,
  Loader2,
  XCircle,
  GitBranch,
  Filter,
  ChevronDown,
  ChevronRight,
  AlertCircle,
} from 'lucide-react';
import type { Epic, Task } from '@/lib/types';

// Column definitions
type KanbanColumn = 'backlog' | 'in_progress' | 'review' | 'done';

const COLUMNS: { id: KanbanColumn; label: string; color: string }[] = [
  { id: 'backlog', label: 'Backlog', color: 'border-gray-500' },
  { id: 'in_progress', label: 'In Progress', color: 'border-blue-500' },
  { id: 'review', label: 'Review', color: 'border-yellow-500' },
  { id: 'done', label: 'Done', color: 'border-green-500' },
];

interface Worktree {
  id: string;
  branch_name: string;
  batch_id: number;
  status: 'pending' | 'active' | 'merged' | 'conflict';
}

interface KanbanTask extends Task {
  worktree_id?: string;
  kanban_status?: KanbanColumn;
  status?: 'pending' | 'running' | 'review' | 'error';
}

interface KanbanBoardProps {
  tasks: KanbanTask[];
  epics: Epic[];
  worktrees?: Worktree[];
  onTaskClick?: (task: KanbanTask) => void;
  onTaskMove?: (taskId: number, newStatus: KanbanColumn) => void;
  className?: string;
}

// Map task status to kanban column
function getKanbanColumn(task: KanbanTask): KanbanColumn {
  if (task.kanban_status) return task.kanban_status;
  if (task.done) return 'done';
  if (task.status === 'running') return 'in_progress';
  if (task.status === 'review') return 'review';
  return 'backlog';
}

// Get status icon
function getStatusIcon(column: KanbanColumn) {
  switch (column) {
    case 'done':
      return <CheckCircle className="w-3 h-3 text-green-400" />;
    case 'in_progress':
      return <Loader2 className="w-3 h-3 text-blue-400 animate-spin" />;
    case 'review':
      return <AlertCircle className="w-3 h-3 text-yellow-400" />;
    default:
      return <Circle className="w-3 h-3 text-gray-400" />;
  }
}

// Task Card Component
function TaskCard({
  task,
  epic,
  worktree,
  onClick,
}: {
  task: KanbanTask;
  epic?: Epic;
  worktree?: Worktree;
  onClick?: () => void;
}) {
  const column = getKanbanColumn(task);

  return (
    <div
      onClick={onClick}
      className={`
        bg-gray-800 border border-gray-700 rounded-lg p-3
        hover:border-gray-600 cursor-pointer transition-colors
        ${task.status === 'error' ? 'border-red-500/50' : ''}
      `}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          {getStatusIcon(column)}
          <span className="text-xs font-medium text-gray-300">
            Task #{task.id}
          </span>
        </div>
        <span className={`text-xs px-1.5 py-0.5 rounded ${
          task.priority === 1 ? 'bg-red-500/20 text-red-400' :
          task.priority === 2 ? 'bg-yellow-500/20 text-yellow-400' :
          'bg-gray-500/20 text-gray-400'
        }`}>
          {task.priority === 1 ? 'high' : task.priority === 2 ? 'medium' : 'low'}
        </span>
      </div>

      {/* Description */}
      <p className="text-xs text-gray-400 mb-2 line-clamp-2">
        {task.description}
      </p>

      {/* Footer */}
      <div className="flex items-center justify-between text-xs">
        {epic && (
          <span className="text-gray-500 truncate max-w-[120px]" title={epic.name}>
            {epic.name}
          </span>
        )}
        {worktree && (
          <span className="flex items-center gap-1 text-blue-400">
            <GitBranch className="w-3 h-3" />
            <span className="truncate max-w-[80px]">{worktree.branch_name}</span>
          </span>
        )}
      </div>
    </div>
  );
}

// Kanban Column Component
function KanbanColumn({
  column,
  tasks,
  epics,
  worktrees,
  onTaskClick,
}: {
  column: typeof COLUMNS[0];
  tasks: KanbanTask[];
  epics: Epic[];
  worktrees?: Worktree[];
  onTaskClick?: (task: KanbanTask) => void;
}) {
  const epicMap = useMemo(() =>
    new Map(epics.map(e => [e.id, e])),
    [epics]
  );

  const worktreeMap = useMemo(() =>
    new Map((worktrees || []).map(w => [w.id, w])),
    [worktrees]
  );

  return (
    <div className="flex-1 min-w-[280px] max-w-[320px]">
      {/* Column Header */}
      <div className={`border-t-2 ${column.color} bg-gray-900 rounded-t-lg p-3 mb-2`}>
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-100">{column.label}</h3>
          <span className="text-xs text-gray-400 bg-gray-800 px-2 py-0.5 rounded">
            {tasks.length}
          </span>
        </div>
      </div>

      {/* Task List */}
      <div className="space-y-2 min-h-[400px] max-h-[600px] overflow-y-auto p-1">
        {tasks.length === 0 ? (
          <div className="text-center py-8 text-xs text-gray-500">
            No tasks
          </div>
        ) : (
          tasks.map(task => (
            <TaskCard
              key={task.id}
              task={task}
              epic={epicMap.get(task.epic_id)}
              worktree={task.worktree_id ? worktreeMap.get(task.worktree_id) : undefined}
              onClick={() => onTaskClick?.(task)}
            />
          ))
        )}
      </div>
    </div>
  );
}

export function KanbanBoard({
  tasks,
  epics,
  worktrees,
  onTaskClick,
  onTaskMove,
  className = '',
}: KanbanBoardProps) {
  const [selectedEpic, setSelectedEpic] = useState<number | null>(null);
  const [showFilters, setShowFilters] = useState(false);

  // Group tasks by column
  const tasksByColumn = useMemo(() => {
    const filtered = selectedEpic
      ? tasks.filter(t => t.epic_id === selectedEpic)
      : tasks;

    const grouped: Record<KanbanColumn, KanbanTask[]> = {
      backlog: [],
      in_progress: [],
      review: [],
      done: [],
    };

    filtered.forEach(task => {
      const column = getKanbanColumn(task);
      grouped[column].push(task);
    });

    // Sort each column by priority (1=high, 2=medium, 3=low)
    Object.keys(grouped).forEach(key => {
      grouped[key as KanbanColumn].sort((a, b) => a.priority - b.priority);
    });

    return grouped;
  }, [tasks, selectedEpic]);

  // Statistics
  const stats = useMemo(() => {
    const total = tasks.length;
    const done = tasksByColumn.done.length;
    const inProgress = tasksByColumn.in_progress.length;
    return { total, done, inProgress, percent: total > 0 ? Math.round((done / total) * 100) : 0 };
  }, [tasks, tasksByColumn]);

  return (
    <div className={`${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-4">
          <h2 className="text-lg font-semibold text-gray-100">Task Board</h2>
          <div className="flex items-center gap-2 text-xs text-gray-400">
            <span>{stats.done}/{stats.total} tasks</span>
            <span className="text-green-400">({stats.percent}%)</span>
          </div>
        </div>

        {/* Filters */}
        <div className="relative">
          <button
            onClick={() => setShowFilters(!showFilters)}
            className="flex items-center gap-2 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded-lg text-xs text-gray-300 transition-colors"
          >
            <Filter className="w-3 h-3" />
            <span>Filter</span>
            {showFilters ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
          </button>

          {showFilters && (
            <div className="absolute right-0 mt-2 w-56 bg-gray-800 border border-gray-700 rounded-lg shadow-xl z-10 p-2">
              <div className="text-xs text-gray-400 px-2 py-1 mb-1">Filter by Epic</div>
              <button
                onClick={() => setSelectedEpic(null)}
                className={`w-full text-left px-2 py-1.5 rounded text-xs transition-colors ${
                  selectedEpic === null ? 'bg-blue-500/20 text-blue-400' : 'text-gray-300 hover:bg-gray-700'
                }`}
              >
                All Epics
              </button>
              {epics.map(epic => (
                <button
                  key={epic.id}
                  onClick={() => setSelectedEpic(epic.id)}
                  className={`w-full text-left px-2 py-1.5 rounded text-xs transition-colors truncate ${
                    selectedEpic === epic.id ? 'bg-blue-500/20 text-blue-400' : 'text-gray-300 hover:bg-gray-700'
                  }`}
                >
                  {epic.name}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Kanban Columns */}
      <div className="flex gap-4 overflow-x-auto pb-4">
        {COLUMNS.map(column => (
          <KanbanColumn
            key={column.id}
            column={column}
            tasks={tasksByColumn[column.id]}
            epics={epics}
            worktrees={worktrees}
            onTaskClick={onTaskClick}
          />
        ))}
      </div>

      {/* Legend */}
      <div className="mt-4 flex items-center gap-6 text-xs text-gray-500">
        <span className="font-medium text-gray-400">Priority:</span>
        <div className="flex items-center gap-1">
          <span className="px-1.5 py-0.5 rounded bg-red-500/20 text-red-400">high</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="px-1.5 py-0.5 rounded bg-yellow-500/20 text-yellow-400">medium</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="px-1.5 py-0.5 rounded bg-gray-500/20 text-gray-400">low</span>
        </div>
      </div>
    </div>
  );
}
