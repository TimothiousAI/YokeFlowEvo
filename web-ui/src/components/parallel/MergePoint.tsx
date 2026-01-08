'use client';

import React from 'react';
import {
  GitMerge,
  CheckCircle,
  XCircle,
  Loader2,
  Cpu,
  AlertTriangle,
  ChevronDown,
  RefreshCw,
  SkipForward,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type { MergeInfo, WorktreeInfo } from './hooks/useParallelState';

interface MergePointProps {
  merge: MergeInfo;
  onForceMerge?: () => void;
  onSkip?: () => void;
  onRetry?: () => void;
  className?: string;
}

function formatModel(model: string): string {
  if (model.includes('opus')) return 'Opus';
  if (model.includes('sonnet')) return 'Sonnet';
  if (model.includes('haiku')) return 'Haiku';
  return model.split('-').pop() || model;
}

function getWorktreeStatusIcon(status: WorktreeInfo['status']) {
  switch (status) {
    case 'merged':
      return <CheckCircle className="w-4 h-4 text-green-400" />;
    case 'active':
      return <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />;
    case 'conflict':
      return <XCircle className="w-4 h-4 text-red-400" />;
    case 'pending':
    default:
      return <div className="w-4 h-4 rounded-full border-2 border-gray-500" />;
  }
}

export function MergePoint({
  merge,
  onForceMerge,
  onSkip,
  onRetry,
  className,
}: MergePointProps) {
  const isWaiting = merge.completedCount < merge.totalCount;
  const hasConflict = merge.worktreesToMerge.some(w => w.status === 'conflict');
  const isComplete = merge.completedCount === merge.totalCount && !hasConflict;

  return (
    <div
      className={cn(
        'relative rounded-lg border-2 bg-gray-800/80 backdrop-blur-sm transition-all duration-300',
        isComplete ? 'border-green-500/50 bg-green-500/5' :
        hasConflict ? 'border-red-500/50 bg-red-500/5' :
        'border-yellow-500/50 bg-yellow-500/5',
        className
      )}
    >
      {/* Connector Lines */}
      <div className="absolute -top-4 left-1/2 transform -translate-x-1/2 w-0.5 h-4 bg-gray-600" />
      <div className="absolute -bottom-4 left-1/2 transform -translate-x-1/2 w-0.5 h-4 bg-gray-600" />

      {/* Arrow indicator */}
      <div className="absolute -top-2 left-1/2 transform -translate-x-1/2">
        <ChevronDown className="w-4 h-4 text-gray-500" />
      </div>

      <div className="p-4">
        {/* Header */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <GitMerge className={cn(
              'w-5 h-5',
              isComplete ? 'text-green-400' :
              hasConflict ? 'text-red-400' :
              'text-yellow-400 animate-pulse'
            )} />
            <span className="font-semibold text-gray-100">
              MERGE POINT
            </span>
            {hasConflict && (
              <span className="px-2 py-0.5 rounded text-xs font-medium bg-red-500/20 text-red-400 border border-red-500/30">
                Conflict
              </span>
            )}
          </div>

          {/* Agent Badge */}
          <div className="flex items-center gap-1 px-2 py-1 rounded-full bg-blue-500/20 border border-blue-500/30">
            <Cpu className="w-3 h-3 text-blue-400" />
            <span className="text-xs text-blue-400">{formatModel(merge.agent)}</span>
          </div>
        </div>

        {/* Status */}
        <div className="text-sm text-gray-400 mb-3">
          {isWaiting ? (
            <span className="flex items-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin" />
              Waiting: {merge.completedCount}/{merge.totalCount} worktrees ready
            </span>
          ) : hasConflict ? (
            <span className="flex items-center gap-2 text-red-400">
              <AlertTriangle className="w-4 h-4" />
              Merge conflicts detected - intervention required
            </span>
          ) : (
            <span className="flex items-center gap-2 text-green-400">
              <CheckCircle className="w-4 h-4" />
              All worktrees merged successfully
            </span>
          )}
        </div>

        {/* Worktrees List */}
        <div className="space-y-2 mb-4">
          <p className="text-xs text-gray-500 uppercase tracking-wide">
            Worktrees to merge:
          </p>
          <div className="space-y-1.5">
            {merge.worktreesToMerge.map(wt => (
              <div
                key={wt.id}
                className={cn(
                  'flex items-center gap-2 px-3 py-2 rounded-lg border',
                  wt.status === 'merged' && 'bg-green-500/10 border-green-500/30',
                  wt.status === 'active' && 'bg-blue-500/10 border-blue-500/30',
                  wt.status === 'conflict' && 'bg-red-500/10 border-red-500/30',
                  wt.status === 'pending' && 'bg-gray-800 border-gray-700',
                )}
              >
                {getWorktreeStatusIcon(wt.status)}
                <span className="font-mono text-sm text-gray-300 truncate flex-1">
                  {wt.branch}
                </span>
                <span className={cn(
                  'text-xs px-1.5 py-0.5 rounded',
                  wt.status === 'merged' && 'bg-green-500/20 text-green-400',
                  wt.status === 'active' && 'bg-blue-500/20 text-blue-400',
                  wt.status === 'conflict' && 'bg-red-500/20 text-red-400',
                  wt.status === 'pending' && 'bg-gray-700 text-gray-400',
                )}>
                  {wt.status}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Action Buttons */}
        {(hasConflict || isWaiting) && (
          <div className="flex items-center gap-2 pt-3 border-t border-gray-700">
            {hasConflict && onRetry && (
              <button
                onClick={onRetry}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-blue-500/20 hover:bg-blue-500/30 text-blue-400 text-sm transition-colors"
              >
                <RefreshCw className="w-3 h-3" />
                Retry Merge
              </button>
            )}
            {onForceMerge && (
              <button
                onClick={onForceMerge}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-yellow-500/20 hover:bg-yellow-500/30 text-yellow-400 text-sm transition-colors"
              >
                <GitMerge className="w-3 h-3" />
                Force Merge
              </button>
            )}
            {onSkip && (
              <button
                onClick={onSkip}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-700/50 hover:bg-gray-700 text-gray-300 text-sm transition-colors"
              >
                <SkipForward className="w-3 h-3" />
                Skip
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
