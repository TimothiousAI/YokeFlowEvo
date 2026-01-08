/**
 * ExecutionTimeline - Timeline/Gantt view of batch execution plan
 *
 * Features:
 * - Horizontal timeline with batch blocks
 * - Show batch dependencies (arrows)
 * - Highlight current batch
 * - Color-coded by status (pending, running, completed)
 * - Task count per batch
 * - Hover for task details
 */

'use client';

import React, { useMemo } from 'react';
import {
  CheckCircle,
  Circle,
  Loader2,
  ChevronRight,
  Zap,
  GitBranch,
} from 'lucide-react';

interface Batch {
  batch_id: number;
  task_ids: number[];
  can_parallel: boolean;
  depends_on?: number[];
  status?: 'pending' | 'running' | 'completed';
}

interface ExecutionPlan {
  batches: Batch[];
  worktree_assignments?: Record<string, string>;
  created_at?: string;
}

interface ExecutionTimelineProps {
  executionPlan: ExecutionPlan;
  currentBatch?: number;
  completedTasks?: number[];
  className?: string;
}

// Get batch status based on current batch and completed tasks
function getBatchStatus(
  batch: Batch,
  currentBatch?: number,
  completedTasks: number[] = []
): 'pending' | 'running' | 'completed' {
  if (batch.status) return batch.status;

  // Check if all tasks in batch are completed
  const allCompleted = batch.task_ids.every(id => completedTasks.includes(id));
  if (allCompleted) return 'completed';

  // Check if this is the current batch
  if (currentBatch === batch.batch_id) return 'running';

  // Check if any task in batch is in progress
  const someCompleted = batch.task_ids.some(id => completedTasks.includes(id));
  if (someCompleted) return 'running';

  return 'pending';
}

// Get status styling
function getStatusStyle(status: 'pending' | 'running' | 'completed') {
  switch (status) {
    case 'completed':
      return {
        bg: 'bg-green-500/20',
        border: 'border-green-500/50',
        text: 'text-green-400',
        icon: <CheckCircle className="w-4 h-4 text-green-400" />,
      };
    case 'running':
      return {
        bg: 'bg-blue-500/20',
        border: 'border-blue-500/50',
        text: 'text-blue-400',
        icon: <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />,
      };
    default:
      return {
        bg: 'bg-gray-800',
        border: 'border-gray-700',
        text: 'text-gray-400',
        icon: <Circle className="w-4 h-4 text-gray-500" />,
      };
  }
}

// Batch Block Component
function BatchBlock({
  batch,
  status,
  isLast,
}: {
  batch: Batch;
  status: 'pending' | 'running' | 'completed';
  isLast: boolean;
}) {
  const style = getStatusStyle(status);
  const taskCount = batch.task_ids.length;

  return (
    <div className="flex items-center">
      {/* Batch Block */}
      <div className={`relative p-4 rounded-lg border ${style.bg} ${style.border} min-w-[140px]`}>
        {/* Header */}
        <div className="flex items-center justify-between mb-2">
          <span className={`text-sm font-semibold ${style.text}`}>
            Batch {batch.batch_id}
          </span>
          {style.icon}
        </div>

        {/* Info */}
        <div className="space-y-1 text-xs">
          <div className="flex items-center gap-2 text-gray-400">
            <span>{taskCount} task{taskCount !== 1 ? 's' : ''}</span>
          </div>

          <div className="flex items-center gap-1">
            {batch.can_parallel ? (
              <>
                <Zap className="w-3 h-3 text-blue-400" />
                <span className="text-blue-400">Parallel</span>
              </>
            ) : (
              <>
                <ChevronRight className="w-3 h-3 text-gray-500" />
                <span className="text-gray-500">Sequential</span>
              </>
            )}
          </div>
        </div>

        {/* Task IDs Tooltip */}
        <div className="mt-2 text-xs text-gray-500 truncate" title={batch.task_ids.join(', ')}>
          Tasks: {batch.task_ids.slice(0, 3).join(', ')}
          {batch.task_ids.length > 3 && `...+${batch.task_ids.length - 3}`}
        </div>

        {/* Current indicator */}
        {status === 'running' && (
          <div className="absolute -top-1 -right-1 w-3 h-3 bg-blue-500 rounded-full animate-pulse" />
        )}
      </div>

      {/* Connector Arrow */}
      {!isLast && (
        <div className="flex items-center px-2">
          <div className="w-8 h-0.5 bg-gray-700" />
          <ChevronRight className="w-4 h-4 text-gray-600 -ml-1" />
        </div>
      )}
    </div>
  );
}

export function ExecutionTimeline({
  executionPlan,
  currentBatch,
  completedTasks = [],
  className = '',
}: ExecutionTimelineProps) {
  const batches = executionPlan.batches || [];

  // Calculate statistics
  const stats = useMemo(() => {
    const total = batches.length;
    const completed = batches.filter(
      b => getBatchStatus(b, currentBatch, completedTasks) === 'completed'
    ).length;
    const running = batches.filter(
      b => getBatchStatus(b, currentBatch, completedTasks) === 'running'
    ).length;
    const totalTasks = batches.reduce((sum, b) => sum + b.task_ids.length, 0);
    const completedTaskCount = completedTasks.length;
    const parallelBatches = batches.filter(b => b.can_parallel).length;

    return {
      total,
      completed,
      running,
      pending: total - completed - running,
      totalTasks,
      completedTaskCount,
      parallelBatches,
      percent: total > 0 ? Math.round((completed / total) * 100) : 0,
    };
  }, [batches, currentBatch, completedTasks]);

  if (batches.length === 0) {
    return (
      <div className={`bg-gray-900 border border-gray-800 rounded-lg p-6 text-center ${className}`}>
        <GitBranch className="w-8 h-8 text-gray-600 mx-auto mb-2" />
        <p className="text-sm text-gray-400">No execution plan available</p>
        <p className="text-xs text-gray-500 mt-1">
          Run initialization to build the execution plan
        </p>
      </div>
    );
  }

  return (
    <div className={className}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-gray-100">Execution Timeline</h3>
        <div className="flex items-center gap-4 text-xs text-gray-400">
          <span>{stats.completed}/{stats.total} batches</span>
          <span>{stats.completedTaskCount}/{stats.totalTasks} tasks</span>
          <span className="text-blue-400">{stats.parallelBatches} parallel</span>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="mb-4">
        <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-green-500 to-blue-500 transition-all duration-500"
            style={{ width: `${stats.percent}%` }}
          />
        </div>
        <div className="flex items-center justify-between mt-1 text-xs text-gray-500">
          <span>Start</span>
          <span>{stats.percent}% complete</span>
          <span>End</span>
        </div>
      </div>

      {/* Timeline */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 overflow-x-auto">
        <div className="flex items-center min-w-max">
          {batches.map((batch, index) => (
            <BatchBlock
              key={batch.batch_id}
              batch={batch}
              status={getBatchStatus(batch, currentBatch, completedTasks)}
              isLast={index === batches.length - 1}
            />
          ))}
        </div>
      </div>

      {/* Legend */}
      <div className="mt-4 flex items-center gap-6 text-xs text-gray-500">
        <div className="flex items-center gap-2">
          <Circle className="w-3 h-3 text-gray-500" />
          <span>Pending</span>
        </div>
        <div className="flex items-center gap-2">
          <Loader2 className="w-3 h-3 text-blue-400" />
          <span>Running</span>
        </div>
        <div className="flex items-center gap-2">
          <CheckCircle className="w-3 h-3 text-green-400" />
          <span>Completed</span>
        </div>
        <div className="flex items-center gap-2">
          <Zap className="w-3 h-3 text-blue-400" />
          <span>Parallel batch</span>
        </div>
      </div>
    </div>
  );
}
