/**
 * ParallelControlPanel - Control panel for managing parallel execution
 *
 * Features:
 * - Start/Stop parallel execution buttons
 * - Pause/Resume current batch
 * - Force sequential toggle
 * - Manual merge trigger
 * - Execution mode indicator
 * - Current batch info
 */

'use client';

import React, { useState } from 'react';
import {
  Play,
  Square,
  Pause,
  SkipForward,
  GitMerge,
  Zap,
  ArrowRight,
  AlertTriangle,
  Loader2,
  Settings,
  RefreshCw,
} from 'lucide-react';

type ExecutionMode = 'idle' | 'sequential' | 'parallel' | 'parallel_running' | 'paused';

interface ParallelControlPanelProps {
  projectId: string;
  executionMode: ExecutionMode;
  currentBatch?: number;
  totalBatches?: number;
  hasExecutionPlan?: boolean;
  isLoading?: boolean;
  onStart?: () => void;
  onStop?: () => void;
  onPause?: () => void;
  onResume?: () => void;
  onMerge?: () => void;
  onRebuildPlan?: () => void;
  className?: string;
}

// Mode styling
const getModeStyle = (mode: ExecutionMode) => {
  switch (mode) {
    case 'parallel_running':
      return {
        bg: 'bg-blue-500/20',
        border: 'border-blue-500/50',
        text: 'text-blue-400',
        label: 'Parallel Execution',
        icon: <Zap className="w-4 h-4" />,
      };
    case 'paused':
      return {
        bg: 'bg-yellow-500/20',
        border: 'border-yellow-500/50',
        text: 'text-yellow-400',
        label: 'Paused',
        icon: <Pause className="w-4 h-4" />,
      };
    case 'sequential':
      return {
        bg: 'bg-gray-700',
        border: 'border-gray-600',
        text: 'text-gray-300',
        label: 'Sequential Mode',
        icon: <ArrowRight className="w-4 h-4" />,
      };
    case 'parallel':
      return {
        bg: 'bg-green-500/20',
        border: 'border-green-500/50',
        text: 'text-green-400',
        label: 'Parallel Ready',
        icon: <Zap className="w-4 h-4" />,
      };
    default:
      return {
        bg: 'bg-gray-800',
        border: 'border-gray-700',
        text: 'text-gray-400',
        label: 'Idle',
        icon: <Settings className="w-4 h-4" />,
      };
  }
};

export function ParallelControlPanel({
  projectId,
  executionMode,
  currentBatch,
  totalBatches,
  hasExecutionPlan = false,
  isLoading = false,
  onStart,
  onStop,
  onPause,
  onResume,
  onMerge,
  onRebuildPlan,
  className = '',
}: ParallelControlPanelProps) {
  const [showAdvanced, setShowAdvanced] = useState(false);

  const modeStyle = getModeStyle(executionMode);
  const isRunning = executionMode === 'parallel_running';
  const isPaused = executionMode === 'paused';
  const canStart = hasExecutionPlan && (executionMode === 'idle' || executionMode === 'parallel');
  const canPause = isRunning;
  const canResume = isPaused;
  const canStop = isRunning || isPaused;

  return (
    <div className={`bg-gray-900 border border-gray-800 rounded-lg ${className}`}>
      {/* Header */}
      <div className="p-4 border-b border-gray-800">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-100">Execution Control</h3>
          <button
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="text-xs text-gray-400 hover:text-gray-300 transition-colors"
          >
            {showAdvanced ? 'Hide' : 'Show'} advanced
          </button>
        </div>
      </div>

      {/* Mode Indicator */}
      <div className="p-4 border-b border-gray-800">
        <div className={`flex items-center gap-3 p-3 rounded-lg border ${modeStyle.bg} ${modeStyle.border}`}>
          <div className={modeStyle.text}>{modeStyle.icon}</div>
          <div className="flex-1">
            <div className={`text-sm font-medium ${modeStyle.text}`}>
              {modeStyle.label}
            </div>
            {currentBatch && totalBatches && (
              <div className="text-xs text-gray-400">
                Batch {currentBatch} of {totalBatches}
              </div>
            )}
          </div>
          {isRunning && <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />}
        </div>
      </div>

      {/* No Execution Plan Warning */}
      {!hasExecutionPlan && (
        <div className="p-4 border-b border-gray-800">
          <div className="flex items-start gap-3 p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
            <AlertTriangle className="w-4 h-4 text-yellow-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-xs text-yellow-400 font-medium">No execution plan</p>
              <p className="text-xs text-gray-400 mt-1">
                Run initialization (Session 0) to build the execution plan.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Main Controls */}
      <div className="p-4 space-y-3">
        {/* Primary Actions */}
        <div className="flex gap-2">
          {/* Start Button */}
          {canStart && (
            <button
              onClick={onStart}
              disabled={isLoading}
              className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-green-500/20 hover:bg-green-500/30 text-green-400 border border-green-500/30 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
            >
              {isLoading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Play className="w-4 h-4" />
              )}
              Start Parallel
            </button>
          )}

          {/* Pause Button */}
          {canPause && (
            <button
              onClick={onPause}
              disabled={isLoading}
              className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-yellow-500/20 hover:bg-yellow-500/30 text-yellow-400 border border-yellow-500/30 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
            >
              <Pause className="w-4 h-4" />
              Pause
            </button>
          )}

          {/* Resume Button */}
          {canResume && (
            <button
              onClick={onResume}
              disabled={isLoading}
              className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-blue-500/20 hover:bg-blue-500/30 text-blue-400 border border-blue-500/30 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
            >
              <SkipForward className="w-4 h-4" />
              Resume
            </button>
          )}

          {/* Stop Button */}
          {canStop && (
            <button
              onClick={onStop}
              disabled={isLoading}
              className="flex items-center justify-center gap-2 px-4 py-2 bg-red-500/20 hover:bg-red-500/30 text-red-400 border border-red-500/30 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
            >
              <Square className="w-4 h-4" />
              Stop
            </button>
          )}
        </div>

        {/* Secondary Actions */}
        <div className="flex gap-2">
          {/* Merge Button */}
          {(isRunning || isPaused) && onMerge && (
            <button
              onClick={onMerge}
              disabled={isLoading}
              className="flex-1 flex items-center justify-center gap-2 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 text-gray-300 border border-gray-700 rounded-lg text-xs transition-colors disabled:opacity-50"
            >
              <GitMerge className="w-3 h-3" />
              Trigger Merge
            </button>
          )}

          {/* Rebuild Plan Button */}
          {hasExecutionPlan && onRebuildPlan && !isRunning && !isPaused && (
            <button
              onClick={onRebuildPlan}
              disabled={isLoading}
              className="flex-1 flex items-center justify-center gap-2 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 text-gray-300 border border-gray-700 rounded-lg text-xs transition-colors disabled:opacity-50"
            >
              <RefreshCw className="w-3 h-3" />
              Rebuild Plan
            </button>
          )}
        </div>
      </div>

      {/* Advanced Options */}
      {showAdvanced && (
        <div className="p-4 border-t border-gray-800 space-y-3">
          <h4 className="text-xs font-medium text-gray-400 uppercase tracking-wide">
            Advanced Options
          </h4>

          {/* Force Sequential Toggle */}
          <label className="flex items-center justify-between p-3 bg-gray-800 rounded-lg cursor-pointer hover:bg-gray-750 transition-colors">
            <div>
              <span className="text-sm text-gray-200">Force Sequential</span>
              <p className="text-xs text-gray-500">
                Run all tasks sequentially, ignoring parallel batches
              </p>
            </div>
            <input
              type="checkbox"
              className="w-4 h-4 rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500 focus:ring-offset-gray-900"
            />
          </label>

          {/* Max Concurrency */}
          <div className="p-3 bg-gray-800 rounded-lg">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-200">Max Concurrency</span>
              <span className="text-sm text-blue-400">4</span>
            </div>
            <input
              type="range"
              min="1"
              max="8"
              defaultValue="4"
              className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer"
            />
            <div className="flex justify-between text-xs text-gray-500 mt-1">
              <span>1</span>
              <span>8</span>
            </div>
          </div>
        </div>
      )}

      {/* Footer Info */}
      <div className="px-4 py-3 border-t border-gray-800 text-xs text-gray-500">
        Project: {projectId.substring(0, 8)}...
      </div>
    </div>
  );
}
