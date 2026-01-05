/**
 * ParallelProgress - Progress dashboard for parallel task execution
 *
 * Features:
 * - Batch progress bar showing current batch / total batches
 * - Running agents list with task names and durations
 * - Cost accumulator showing running total
 * - ETA calculation based on historical task durations
 * - Refresh rate control (1s, 5s, 10s)
 */

'use client';

import React, { useState, useEffect } from 'react';
import {
  Activity,
  Clock,
  DollarSign,
  Loader2,
  RefreshCw,
  Zap,
  CheckCircle,
  AlertCircle
} from 'lucide-react';
import { ProgressBar } from './ProgressBar';

interface RunningAgent {
  task_id: number;
  task_description: string;
  epic_name: string;
  model: string;
  started_at: string;
  duration_seconds?: number;
}

interface BatchProgress {
  current_batch: number;
  total_batches: number;
  current_batch_tasks: number;
  completed_batch_tasks: number;
  total_tasks_remaining: number;
}

interface ParallelProgressProps {
  batchProgress: BatchProgress;
  runningAgents: RunningAgent[];
  totalCostUsd: number;
  estimatedTimeRemaining?: number; // seconds
  onRefreshRateChange?: (rate: number) => void;
  refreshRate?: number; // seconds (1, 5, or 10)
  className?: string;
}

export function ParallelProgress({
  batchProgress,
  runningAgents,
  totalCostUsd,
  estimatedTimeRemaining,
  onRefreshRateChange,
  refreshRate = 5,
  className = '',
}: ParallelProgressProps) {
  const [currentTime, setCurrentTime] = useState(Date.now());

  // Update current time every second for duration calculations
  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentTime(Date.now());
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  // Calculate batch completion percentage
  const batchProgressPercent =
    batchProgress.total_batches > 0
      ? ((batchProgress.current_batch - 1) / batchProgress.total_batches) * 100 +
        (batchProgress.current_batch_tasks > 0
          ? (batchProgress.completed_batch_tasks / batchProgress.current_batch_tasks) *
            (100 / batchProgress.total_batches)
          : 0)
      : 0;

  // Format time duration
  const formatDuration = (seconds: number): string => {
    if (seconds < 60) return `${Math.floor(seconds)}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.floor(seconds % 60)}s`;
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${hours}h ${minutes}m`;
  };

  // Calculate agent duration
  const getAgentDuration = (agent: RunningAgent): number => {
    const startTime = new Date(agent.started_at).getTime();
    return Math.floor((currentTime - startTime) / 1000);
  };

  // Refresh rate options
  const refreshRates = [1, 5, 10];

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Header with Refresh Rate Control */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-100 flex items-center gap-2">
          <Activity className="w-5 h-5 text-blue-400" />
          Parallel Execution Progress
        </h3>

        {onRefreshRateChange && (
          <div className="flex items-center gap-2">
            <RefreshCw className="w-4 h-4 text-gray-400" />
            <span className="text-xs text-gray-400">Refresh:</span>
            <div className="flex gap-1">
              {refreshRates.map((rate) => (
                <button
                  key={rate}
                  onClick={() => onRefreshRateChange(rate)}
                  className={`px-2 py-1 text-xs rounded transition-colors ${
                    refreshRate === rate
                      ? 'bg-blue-500 text-white'
                      : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                  }`}
                >
                  {rate}s
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Batch Progress */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Zap className="w-4 h-4 text-blue-400" />
            <span className="text-sm font-medium text-gray-100">Batch Progress</span>
          </div>
          <span className="text-xs text-gray-400">
            Batch {batchProgress.current_batch} of {batchProgress.total_batches}
          </span>
        </div>

        <ProgressBar
          value={batchProgressPercent}
          className="mb-2"
          color="blue"
          showPercentage={true}
        />

        <div className="flex items-center justify-between text-xs text-gray-400">
          <span>
            {batchProgress.completed_batch_tasks}/{batchProgress.current_batch_tasks} tasks in current batch
          </span>
          <span>{batchProgress.total_tasks_remaining} tasks remaining</span>
        </div>
      </div>

      {/* Running Agents */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <div className="flex items-center gap-2 mb-3">
          <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />
          <span className="text-sm font-medium text-gray-100">
            Running Agents ({runningAgents.length})
          </span>
        </div>

        {runningAgents.length === 0 ? (
          <div className="text-center py-4 text-xs text-gray-500">
            No agents currently running
          </div>
        ) : (
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {runningAgents.map((agent) => {
              const duration = getAgentDuration(agent);
              return (
                <div
                  key={agent.task_id}
                  className="bg-gray-800/50 border border-gray-700 rounded-lg p-3"
                >
                  <div className="flex items-start justify-between gap-2 mb-1">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs font-medium text-blue-400">
                          Task #{agent.task_id}
                        </span>
                        <span className="text-xs text-gray-500">•</span>
                        <span className="text-xs text-gray-400 truncate">
                          {agent.epic_name}
                        </span>
                      </div>
                      <p className="text-xs text-gray-300 line-clamp-2">
                        {agent.task_description}
                      </p>
                    </div>
                    <div className="flex-shrink-0 text-right">
                      <div className="text-xs font-mono text-gray-400">
                        {formatDuration(duration)}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 mt-2">
                    <span className="text-xs px-2 py-0.5 rounded bg-blue-500/20 text-blue-400 border border-blue-500/30">
                      {agent.model}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Cost & ETA */}
      <div className="grid grid-cols-2 gap-4">
        {/* Cost Accumulator */}
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <DollarSign className="w-4 h-4 text-green-400" />
            <span className="text-sm font-medium text-gray-100">Total Cost</span>
          </div>
          <div className="text-2xl font-bold text-green-400">
            ${totalCostUsd.toFixed(2)}
          </div>
          <p className="text-xs text-gray-500 mt-1">Running total</p>
        </div>

        {/* ETA */}
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <Clock className="w-4 h-4 text-blue-400" />
            <span className="text-sm font-medium text-gray-100">Estimated Time</span>
          </div>
          {estimatedTimeRemaining !== undefined && estimatedTimeRemaining > 0 ? (
            <>
              <div className="text-2xl font-bold text-blue-400">
                {formatDuration(estimatedTimeRemaining)}
              </div>
              <p className="text-xs text-gray-500 mt-1">Remaining</p>
            </>
          ) : (
            <>
              <div className="text-2xl font-bold text-gray-500">--</div>
              <p className="text-xs text-gray-500 mt-1">Calculating...</p>
            </>
          )}
        </div>
      </div>

      {/* Summary Stats */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <div className="flex items-center justify-center gap-1 mb-1">
              <CheckCircle className="w-3 h-3 text-green-400" />
              <span className="text-xs text-gray-400">Completed</span>
            </div>
            <div className="text-lg font-bold text-green-400">
              {(batchProgress.current_batch - 1) * batchProgress.current_batch_tasks +
                batchProgress.completed_batch_tasks}
            </div>
          </div>

          <div>
            <div className="flex items-center justify-center gap-1 mb-1">
              <Loader2 className="w-3 h-3 text-blue-400" />
              <span className="text-xs text-gray-400">In Progress</span>
            </div>
            <div className="text-lg font-bold text-blue-400">{runningAgents.length}</div>
          </div>

          <div>
            <div className="flex items-center justify-center gap-1 mb-1">
              <AlertCircle className="w-3 h-3 text-gray-400" />
              <span className="text-xs text-gray-400">Remaining</span>
            </div>
            <div className="text-lg font-bold text-gray-400">
              {batchProgress.total_tasks_remaining}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
