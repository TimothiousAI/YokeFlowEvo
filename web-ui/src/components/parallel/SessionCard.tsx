'use client';

import React from 'react';
import {
  Loader2,
  CheckCircle,
  Circle,
  Cpu,
  GitBranch,
  Clock,
  MoreVertical,
  Square,
  Eye,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type { SessionInfo } from './hooks/useParallelState';

interface SessionCardProps {
  session: SessionInfo;
  isRunning: boolean;
  onViewDetails?: () => void;
  onStop?: () => void;
  className?: string;
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  if (mins < 60) return `${mins}m ${secs}s`;
  const hours = Math.floor(mins / 60);
  const remainingMins = mins % 60;
  return `${hours}h ${remainingMins}m`;
}

function formatModel(model: string): string {
  if (model.includes('opus')) return 'Opus';
  if (model.includes('sonnet')) return 'Sonnet';
  if (model.includes('haiku')) return 'Haiku';
  return model.split('-').pop() || model;
}

function getPhaseColor(phase: string): string {
  switch (phase) {
    case 'planning':
      return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
    case 'executing':
      return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
    case 'verifying':
      return 'bg-purple-500/20 text-purple-400 border-purple-500/30';
    case 'completed':
      return 'bg-green-500/20 text-green-400 border-green-500/30';
    default:
      return 'bg-gray-500/20 text-gray-400 border-gray-500/30';
  }
}

export function SessionCard({
  session,
  isRunning,
  onViewDetails,
  onStop,
  className,
}: SessionCardProps) {
  const progressPercent = session.progress.total > 0
    ? Math.round((session.progress.completed / session.progress.total) * 100)
    : 0;

  return (
    <div
      className={cn(
        'relative rounded-lg border bg-gray-800/50 backdrop-blur-sm transition-all duration-200',
        isRunning && 'session-card-running',
        !isRunning && session.phase === 'completed' && 'border-green-500/50 bg-green-500/5',
        !isRunning && session.phase !== 'completed' && 'border-gray-700',
        className
      )}
    >
      {/* Animated border for running sessions */}
      {isRunning && (
        <div className="absolute -inset-[2px] rounded-lg bg-gradient-to-r from-blue-500 via-purple-500 to-blue-500 opacity-75 blur-sm animate-pulse" />
      )}

      <div className={cn(
        'relative rounded-lg bg-gray-800 p-4',
        isRunning && 'bg-gray-800/95'
      )}>
        {/* Header */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            {isRunning ? (
              <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />
            ) : session.phase === 'completed' ? (
              <CheckCircle className="w-4 h-4 text-green-400" />
            ) : (
              <Circle className="w-4 h-4 text-gray-500" />
            )}
            <span className="font-medium text-gray-100">
              Task #{session.taskId}
            </span>
          </div>

          <div className="flex items-center gap-1">
            {onViewDetails && (
              <button
                onClick={onViewDetails}
                className="p-1 rounded hover:bg-gray-700 text-gray-400 hover:text-gray-200 transition-colors"
                title="View details"
              >
                <Eye className="w-4 h-4" />
              </button>
            )}
            {onStop && isRunning && (
              <button
                onClick={onStop}
                className="p-1 rounded hover:bg-red-500/20 text-gray-400 hover:text-red-400 transition-colors"
                title="Stop task"
              >
                <Square className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>

        {/* Task Description */}
        <p className="text-sm text-gray-300 mb-3 line-clamp-2">
          {session.taskDescription}
        </p>

        {/* Model & Phase Badges */}
        <div className="flex items-center gap-2 mb-3 flex-wrap">
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-blue-500/20 text-blue-400 border border-blue-500/30">
            <Cpu className="w-3 h-3" />
            {formatModel(session.model)}
          </span>
          <span className={cn(
            'inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium border',
            getPhaseColor(session.phase)
          )}>
            {session.phase}
          </span>
        </div>

        {/* Progress Bar */}
        <div className="mb-3">
          <div className="flex items-center justify-between text-xs text-gray-400 mb-1">
            <span>Progress</span>
            <span>{session.progress.completed}/{session.progress.total} tasks</span>
          </div>
          <div className="h-1.5 bg-gray-700 rounded-full overflow-hidden">
            <div
              className={cn(
                'h-full rounded-full transition-all duration-500',
                progressPercent === 100 ? 'bg-green-500' : 'bg-blue-500'
              )}
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>

        {/* Progress Dots */}
        <div className="flex items-center gap-1 mb-3">
          {Array.from({ length: session.progress.total }).map((_, i) => (
            <div
              key={i}
              className={cn(
                'w-2 h-2 rounded-full transition-colors',
                i < session.progress.completed
                  ? 'bg-green-500'
                  : i === session.progress.completed && isRunning
                    ? 'bg-blue-500 animate-pulse'
                    : 'bg-gray-600'
              )}
            />
          ))}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between text-xs text-gray-500">
          {session.worktreeBranch && (
            <div className="flex items-center gap-1">
              <GitBranch className="w-3 h-3" />
              <span className="font-mono truncate max-w-[120px]">
                {session.worktreeBranch}
              </span>
            </div>
          )}
          <div className="flex items-center gap-1">
            <Clock className="w-3 h-3" />
            <span>{formatDuration(session.duration)}</span>
          </div>
        </div>

        {/* Epic name */}
        {session.epicName && (
          <div className="mt-2 pt-2 border-t border-gray-700">
            <span className="text-xs text-gray-500">
              Epic: {session.epicName}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

// Add CSS for animated border
const styles = `
@keyframes border-flow {
  0% { background-position: 0% 50%; }
  100% { background-position: 200% 50%; }
}

.session-card-running::before {
  content: '';
  position: absolute;
  inset: -2px;
  border-radius: 0.5rem;
  background: linear-gradient(90deg, #3b82f6, #8b5cf6, #ec4899, #3b82f6);
  background-size: 300% 100%;
  animation: border-flow 3s linear infinite;
  z-index: -1;
}
`;

// Inject styles
if (typeof document !== 'undefined') {
  const styleSheet = document.createElement('style');
  styleSheet.textContent = styles;
  document.head.appendChild(styleSheet);
}
