'use client';

import React from 'react';
import {
  ChevronDown,
  ChevronRight,
  Loader2,
  CheckCircle,
  XCircle,
  Clock,
  GitMerge,
  Layers,
  AlertCircle,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { SessionCard } from './SessionCard';
import type { BatchState, SessionInfo, WorktreeInfo } from './hooks/useParallelState';

interface BatchCardProps {
  batch: BatchState;
  sessions: SessionInfo[];
  worktrees: WorktreeInfo[];
  isExpanded: boolean;
  onToggleExpand: () => void;
  onViewSessionDetails?: (taskId: number) => void;
  onStopSession?: (taskId: number) => void;
  className?: string;
}

function getStatusIcon(status: BatchState['status']) {
  switch (status) {
    case 'running':
      return <Loader2 className="w-5 h-5 text-blue-400 animate-spin" />;
    case 'merging':
      return <GitMerge className="w-5 h-5 text-yellow-400 animate-pulse" />;
    case 'completed':
      return <CheckCircle className="w-5 h-5 text-green-400" />;
    case 'failed':
      return <XCircle className="w-5 h-5 text-red-400" />;
    case 'queued':
    default:
      return <Clock className="w-5 h-5 text-gray-400" />;
  }
}

function getStatusLabel(status: BatchState['status']) {
  switch (status) {
    case 'running':
      return 'Running';
    case 'merging':
      return 'Merging';
    case 'completed':
      return 'Completed';
    case 'failed':
      return 'Failed';
    case 'queued':
    default:
      return 'Queued';
  }
}

function getBorderColor(status: BatchState['status']) {
  switch (status) {
    case 'running':
      return 'border-blue-500/50';
    case 'merging':
      return 'border-yellow-500/50';
    case 'completed':
      return 'border-green-500/50';
    case 'failed':
      return 'border-red-500/50';
    case 'queued':
    default:
      return 'border-gray-700';
  }
}

function getBackgroundColor(status: BatchState['status']) {
  switch (status) {
    case 'running':
      return 'bg-blue-500/5';
    case 'merging':
      return 'bg-yellow-500/5';
    case 'completed':
      return 'bg-green-500/5';
    case 'failed':
      return 'bg-red-500/5';
    case 'queued':
    default:
      return 'bg-gray-800/50';
  }
}

export function BatchCard({
  batch,
  sessions,
  worktrees,
  isExpanded,
  onToggleExpand,
  onViewSessionDetails,
  onStopSession,
  className,
}: BatchCardProps) {
  const completedTasks = sessions.filter(s => s.phase === 'completed').length;
  const totalTasks = batch.taskIds.length;
  const progressPercent = totalTasks > 0 ? Math.round((completedTasks / totalTasks) * 100) : 0;

  // Get worktrees for this batch's tasks
  const batchWorktrees = worktrees.filter(w =>
    sessions.some(s => s.worktreeBranch === w.branch)
  );

  return (
    <div
      className={cn(
        'rounded-xl border-2 transition-all duration-300',
        getBorderColor(batch.status),
        getBackgroundColor(batch.status),
        className
      )}
    >
      {/* Batch Header */}
      <button
        onClick={onToggleExpand}
        className="w-full p-4 flex items-center justify-between hover:bg-white/5 transition-colors rounded-t-xl"
      >
        <div className="flex items-center gap-3">
          {/* Expand/Collapse Icon */}
          {isExpanded ? (
            <ChevronDown className="w-5 h-5 text-gray-400" />
          ) : (
            <ChevronRight className="w-5 h-5 text-gray-400" />
          )}

          {/* Batch Icon */}
          <div className="flex items-center gap-2">
            <Layers className="w-5 h-5 text-gray-400" />
            <span className="font-semibold text-gray-100">
              Batch {batch.batchId}
            </span>
          </div>

          {/* Status Badge */}
          <div className="flex items-center gap-2 px-2 py-1 rounded-full bg-gray-800/80 border border-gray-700">
            {getStatusIcon(batch.status)}
            <span className="text-sm text-gray-300">
              {getStatusLabel(batch.status)}
            </span>
          </div>

          {/* Parallel indicator */}
          {batch.canParallel && batch.taskIds.length > 1 && (
            <span className="text-xs px-2 py-0.5 rounded bg-purple-500/20 text-purple-400 border border-purple-500/30">
              Parallel ({batch.taskIds.length} tasks)
            </span>
          )}
        </div>

        {/* Right side info */}
        <div className="flex items-center gap-4 text-sm text-gray-400">
          {/* Dependencies */}
          {batch.dependsOn.length > 0 && (
            <span className="flex items-center gap-1">
              <AlertCircle className="w-4 h-4" />
              Depends on: Batch {batch.dependsOn.join(', ')}
            </span>
          )}

          {/* Progress */}
          {batch.status !== 'queued' && (
            <span>
              {completedTasks}/{totalTasks} tasks
            </span>
          )}

          {/* Merge status */}
          {batch.mergeStatus && (
            <span className={cn(
              'px-2 py-0.5 rounded text-xs font-medium',
              batch.mergeStatus === 'success' && 'bg-green-500/20 text-green-400',
              batch.mergeStatus === 'conflict' && 'bg-red-500/20 text-red-400',
              batch.mergeStatus === 'pending' && 'bg-yellow-500/20 text-yellow-400',
            )}>
              Merge: {batch.mergeStatus}
            </span>
          )}
        </div>
      </button>

      {/* Progress Bar (always visible when not queued) */}
      {batch.status !== 'queued' && (
        <div className="px-4 pb-2">
          <div className="h-1 bg-gray-700 rounded-full overflow-hidden">
            <div
              className={cn(
                'h-full rounded-full transition-all duration-500',
                batch.status === 'completed' ? 'bg-green-500' :
                batch.status === 'failed' ? 'bg-red-500' :
                batch.status === 'merging' ? 'bg-yellow-500' : 'bg-blue-500'
              )}
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>
      )}

      {/* Expanded Content */}
      {isExpanded && (
        <div className="p-4 pt-2 border-t border-gray-700/50">
          {/* Session Cards Grid */}
          {sessions.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {sessions.map(session => (
                <SessionCard
                  key={session.taskId}
                  session={session}
                  isRunning={batch.status === 'running' && session.phase !== 'completed'}
                  onViewDetails={onViewSessionDetails ? () => onViewSessionDetails(session.taskId) : undefined}
                  onStop={onStopSession ? () => onStopSession(session.taskId) : undefined}
                />
              ))}
            </div>
          ) : (
            /* Queued tasks preview */
            <div className="space-y-2">
              <p className="text-sm text-gray-400 mb-3">
                Tasks in this batch:
              </p>
              <div className="flex flex-wrap gap-2">
                {batch.taskIds.map(taskId => (
                  <span
                    key={taskId}
                    className="px-3 py-1.5 rounded-lg bg-gray-800 border border-gray-700 text-sm text-gray-300"
                  >
                    Task #{taskId}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Worktrees Info */}
          {batchWorktrees.length > 0 && (
            <div className="mt-4 pt-4 border-t border-gray-700/50">
              <p className="text-xs text-gray-500 mb-2">Worktrees:</p>
              <div className="flex flex-wrap gap-2">
                {batchWorktrees.map(wt => (
                  <span
                    key={wt.id}
                    className={cn(
                      'px-2 py-1 rounded text-xs font-mono',
                      wt.status === 'merged' && 'bg-green-500/20 text-green-400 border border-green-500/30',
                      wt.status === 'active' && 'bg-blue-500/20 text-blue-400 border border-blue-500/30',
                      wt.status === 'conflict' && 'bg-red-500/20 text-red-400 border border-red-500/30',
                      wt.status === 'pending' && 'bg-gray-500/20 text-gray-400 border border-gray-500/30',
                    )}
                  >
                    {wt.branch}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Timing Info */}
          {(batch.startedAt || batch.completedAt) && (
            <div className="mt-4 pt-4 border-t border-gray-700/50 flex items-center gap-4 text-xs text-gray-500">
              {batch.startedAt && (
                <span>Started: {batch.startedAt.toLocaleTimeString()}</span>
              )}
              {batch.completedAt && (
                <span>Completed: {batch.completedAt.toLocaleTimeString()}</span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
