/**
 * WorktreeCard - Card showing worktree status
 *
 * Features:
 * - Branch name and status indicator
 * - Current task being worked on
 * - Agent status (running/idle/error)
 * - Last commit timestamp
 * - Merge readiness indicator
 * - Action buttons (merge, delete)
 */

'use client';

import React from 'react';
import {
  GitBranch,
  GitMerge,
  Loader2,
  CheckCircle,
  AlertTriangle,
  Clock,
  Trash2,
  Circle,
  XCircle,
} from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import type { Task } from '@/lib/types';

interface Worktree {
  id: string;
  branch_name: string;
  batch_id: number;
  status: 'pending' | 'active' | 'merged' | 'conflict';
  created_at: string;
  merged_at?: string;
  last_commit?: string;
  last_commit_at?: string;
}

type AgentStatus = 'running' | 'idle' | 'error';

interface WorktreeCardProps {
  worktree: Worktree;
  currentTask?: Task;
  agentStatus?: AgentStatus;
  onMerge?: () => void;
  onDelete?: () => void;
  className?: string;
}

// Status color mapping
const getStatusColor = (status: Worktree['status']) => {
  switch (status) {
    case 'active':
      return 'border-blue-500 bg-blue-500/10';
    case 'merged':
      return 'border-green-500 bg-green-500/10';
    case 'conflict':
      return 'border-red-500 bg-red-500/10';
    default:
      return 'border-gray-700 bg-gray-800';
  }
};

const getStatusIcon = (status: Worktree['status']) => {
  switch (status) {
    case 'active':
      return <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />;
    case 'merged':
      return <CheckCircle className="w-4 h-4 text-green-400" />;
    case 'conflict':
      return <AlertTriangle className="w-4 h-4 text-red-400" />;
    default:
      return <Circle className="w-4 h-4 text-gray-400" />;
  }
};

const getStatusLabel = (status: Worktree['status']) => {
  switch (status) {
    case 'active':
      return 'Active';
    case 'merged':
      return 'Merged';
    case 'conflict':
      return 'Conflict';
    default:
      return 'Pending';
  }
};

const getAgentStatusIcon = (status?: AgentStatus) => {
  switch (status) {
    case 'running':
      return <Loader2 className="w-3 h-3 text-blue-400 animate-spin" />;
    case 'error':
      return <XCircle className="w-3 h-3 text-red-400" />;
    default:
      return <Circle className="w-3 h-3 text-gray-500" />;
  }
};

export function WorktreeCard({
  worktree,
  currentTask,
  agentStatus = 'idle',
  onMerge,
  onDelete,
  className = '',
}: WorktreeCardProps) {
  const canMerge = worktree.status === 'active' && agentStatus !== 'running';
  const showActions = worktree.status !== 'merged';

  return (
    <div className={`border rounded-lg p-4 ${getStatusColor(worktree.status)} ${className}`}>
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <GitBranch className="w-4 h-4 text-gray-400" />
          <span className="text-sm font-medium text-gray-100 truncate max-w-[180px]" title={worktree.branch_name}>
            {worktree.branch_name}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {getStatusIcon(worktree.status)}
          <span className="text-xs text-gray-400">{getStatusLabel(worktree.status)}</span>
        </div>
      </div>

      {/* Current Task */}
      {currentTask && (
        <div className="mb-3 p-2 bg-gray-900/50 rounded border border-gray-700">
          <div className="flex items-center gap-2 mb-1">
            {getAgentStatusIcon(agentStatus)}
            <span className="text-xs text-gray-400">
              {agentStatus === 'running' ? 'Working on' : 'Last task'}:
            </span>
          </div>
          <p className="text-xs text-gray-300 line-clamp-2">
            Task #{currentTask.id}: {currentTask.description}
          </p>
        </div>
      )}

      {/* Info */}
      <div className="space-y-2 text-xs">
        <div className="flex items-center justify-between text-gray-400">
          <span>Batch #{worktree.batch_id}</span>
          <span className="flex items-center gap-1">
            <Clock className="w-3 h-3" />
            {formatDistanceToNow(new Date(worktree.created_at), { addSuffix: true })}
          </span>
        </div>

        {worktree.last_commit && (
          <div className="text-gray-500 truncate" title={worktree.last_commit}>
            Last commit: {worktree.last_commit.substring(0, 40)}...
          </div>
        )}

        {worktree.merged_at && (
          <div className="text-green-400">
            Merged {formatDistanceToNow(new Date(worktree.merged_at), { addSuffix: true })}
          </div>
        )}
      </div>

      {/* Conflict Warning */}
      {worktree.status === 'conflict' && (
        <div className="mt-3 p-2 bg-red-500/10 border border-red-500/30 rounded">
          <div className="flex items-center gap-2 text-xs text-red-400">
            <AlertTriangle className="w-3 h-3" />
            <span>Merge conflicts detected - manual resolution required</span>
          </div>
        </div>
      )}

      {/* Actions */}
      {showActions && (
        <div className="mt-3 flex items-center gap-2">
          {canMerge && onMerge && (
            <button
              onClick={onMerge}
              className="flex items-center gap-1 px-3 py-1.5 bg-green-500/20 hover:bg-green-500/30 text-green-400 border border-green-500/30 rounded text-xs transition-colors"
            >
              <GitMerge className="w-3 h-3" />
              Merge
            </button>
          )}
          {onDelete && worktree.status !== 'active' && (
            <button
              onClick={onDelete}
              className="flex items-center gap-1 px-3 py-1.5 bg-red-500/20 hover:bg-red-500/30 text-red-400 border border-red-500/30 rounded text-xs transition-colors"
            >
              <Trash2 className="w-3 h-3" />
              Delete
            </button>
          )}
        </div>
      )}
    </div>
  );
}
