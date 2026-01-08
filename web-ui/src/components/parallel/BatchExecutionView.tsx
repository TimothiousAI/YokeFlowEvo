'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  Play,
  Pause,
  Square,
  RefreshCw,
  Settings,
  DollarSign,
  Layers,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { BatchCard } from './BatchCard';
import { BatchConnector, MergeConnector, ArrowConnector } from './BatchConnector';
import { MergePoint } from './MergePoint';
import { TaskQueue } from './TaskQueue';
import { ExpertiseMiniPanel } from './ExpertiseMiniPanel';
import { useParallelState } from './hooks/useParallelState';
import type { SessionInfo } from './hooks/useParallelState';

interface BatchExecutionViewProps {
  projectId: string;
  onViewExpertise?: () => void;
  onViewSessionDetails?: (taskId: number) => void;
  className?: string;
}

function formatCost(cost: number): string {
  return `$${cost.toFixed(2)}`;
}

export function BatchExecutionView({
  projectId,
  onViewExpertise,
  onViewSessionDetails,
  className,
}: BatchExecutionViewProps) {
  const {
    isRunning,
    isPaused,
    executionPlan,
    currentBatchIndex,
    batches,
    runningSessions,
    worktrees,
    pendingMerge,
    recentLearnings,
    domainSummaries,
    totalCost,
    startExecution,
    stopExecution,
    pauseExecution,
    resumeExecution,
    rebuildPlan,
    triggerMerge,
    refresh,
  } = useParallelState({ projectId });

  const [expandedBatches, setExpandedBatches] = useState<Set<number>>(new Set());
  const [isLoading, setIsLoading] = useState(false);

  // Auto-expand current batch
  useEffect(() => {
    if (batches.length > 0 && currentBatchIndex < batches.length) {
      const currentBatch = batches[currentBatchIndex];
      setExpandedBatches(prev => new Set(prev).add(currentBatch.batchId));
    }
  }, [currentBatchIndex, batches]);

  const toggleBatchExpand = (batchId: number) => {
    setExpandedBatches(prev => {
      const newSet = new Set(prev);
      if (newSet.has(batchId)) {
        newSet.delete(batchId);
      } else {
        newSet.add(batchId);
      }
      return newSet;
    });
  };

  // Get sessions for a specific batch
  const getSessionsForBatch = useCallback((batch: typeof batches[0]): SessionInfo[] => {
    return runningSessions.filter(s => batch.taskIds.includes(s.taskId));
  }, [runningSessions]);

  // Calculate overall progress
  const completedBatches = batches.filter(b => b.status === 'completed').length;
  const totalBatches = batches.length;
  const completedTasks = batches.reduce((sum, b) => {
    if (b.status === 'completed') return sum + b.taskIds.length;
    const sessions = getSessionsForBatch(b);
    return sum + sessions.filter(s => s.phase === 'completed').length;
  }, 0);
  const totalTasks = executionPlan?.metadata.total_tasks || 0;

  // Upcoming batches (not yet started)
  const upcomingBatches = batches.filter(b => b.status === 'queued');

  // Handle actions
  const handleStart = async () => {
    setIsLoading(true);
    try {
      await startExecution();
    } finally {
      setIsLoading(false);
    }
  };

  const handleStop = async () => {
    setIsLoading(true);
    try {
      await stopExecution();
    } finally {
      setIsLoading(false);
    }
  };

  const handlePause = async () => {
    setIsLoading(true);
    try {
      if (isPaused) {
        await resumeExecution();
      } else {
        await pauseExecution();
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleRebuild = async () => {
    setIsLoading(true);
    try {
      await rebuildPlan();
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className={cn('space-y-4', className)}>
      {/* Header */}
      <div className="flex items-center justify-between p-4 rounded-lg bg-gray-800/50 border border-gray-700">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Layers className="w-6 h-6 text-blue-400" />
            <h2 className="text-xl font-bold text-gray-100">
              Parallel Execution
            </h2>
          </div>

          {/* Status Badge */}
          {isRunning && (
            <span className={cn(
              'px-3 py-1 rounded-full text-sm font-medium',
              isPaused
                ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30'
                : 'bg-blue-500/20 text-blue-400 border border-blue-500/30 animate-pulse'
            )}>
              {isPaused ? 'Paused' : 'Running'}
            </span>
          )}
        </div>

        {/* Controls */}
        <div className="flex items-center gap-2">
          {!isRunning ? (
            <button
              onClick={handleStart}
              disabled={isLoading || batches.length === 0}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-green-500/20 hover:bg-green-500/30 text-green-400 border border-green-500/30 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Play className="w-4 h-4" />
              Start
            </button>
          ) : (
            <>
              <button
                onClick={handlePause}
                disabled={isLoading}
                className={cn(
                  'flex items-center gap-2 px-4 py-2 rounded-lg transition-colors disabled:opacity-50',
                  isPaused
                    ? 'bg-green-500/20 hover:bg-green-500/30 text-green-400 border border-green-500/30'
                    : 'bg-yellow-500/20 hover:bg-yellow-500/30 text-yellow-400 border border-yellow-500/30'
                )}
              >
                {isPaused ? (
                  <>
                    <Play className="w-4 h-4" />
                    Resume
                  </>
                ) : (
                  <>
                    <Pause className="w-4 h-4" />
                    Pause
                  </>
                )}
              </button>
              <button
                onClick={handleStop}
                disabled={isLoading}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-red-500/20 hover:bg-red-500/30 text-red-400 border border-red-500/30 transition-colors disabled:opacity-50"
              >
                <Square className="w-4 h-4" />
                Stop
              </button>
            </>
          )}

          <button
            onClick={handleRebuild}
            disabled={isLoading || isRunning}
            className="p-2 rounded-lg hover:bg-gray-700 text-gray-400 hover:text-gray-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            title="Rebuild execution plan"
          >
            <RefreshCw className={cn('w-5 h-5', isLoading && 'animate-spin')} />
          </button>
        </div>
      </div>

      {/* Progress Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-4 rounded-lg bg-gray-800/50 border border-gray-700">
          <div className="flex items-center gap-2 text-gray-400 text-sm mb-1">
            <CheckCircle2 className="w-4 h-4" />
            Tasks
          </div>
          <div className="text-2xl font-bold text-gray-100">
            {completedTasks}/{totalTasks}
          </div>
          <div className="mt-2 h-1 bg-gray-700 rounded-full overflow-hidden">
            <div
              className="h-full bg-green-500 rounded-full transition-all duration-500"
              style={{ width: totalTasks > 0 ? `${(completedTasks / totalTasks) * 100}%` : '0%' }}
            />
          </div>
        </div>

        <div className="p-4 rounded-lg bg-gray-800/50 border border-gray-700">
          <div className="flex items-center gap-2 text-gray-400 text-sm mb-1">
            <Layers className="w-4 h-4" />
            Batches
          </div>
          <div className="text-2xl font-bold text-gray-100">
            {completedBatches}/{totalBatches}
          </div>
          <div className="mt-2 h-1 bg-gray-700 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-500 rounded-full transition-all duration-500"
              style={{ width: totalBatches > 0 ? `${(completedBatches / totalBatches) * 100}%` : '0%' }}
            />
          </div>
        </div>

        <div className="p-4 rounded-lg bg-gray-800/50 border border-gray-700">
          <div className="flex items-center gap-2 text-gray-400 text-sm mb-1">
            <AlertCircle className="w-4 h-4" />
            Active Sessions
          </div>
          <div className="text-2xl font-bold text-gray-100">
            {runningSessions.length}
          </div>
          <div className="text-xs text-gray-500 mt-2">
            {executionPlan?.metadata.parallel_possible || 0} max parallel
          </div>
        </div>

        <div className="p-4 rounded-lg bg-gray-800/50 border border-gray-700">
          <div className="flex items-center gap-2 text-gray-400 text-sm mb-1">
            <DollarSign className="w-4 h-4" />
            Total Cost
          </div>
          <div className="text-2xl font-bold text-gray-100">
            {formatCost(totalCost)}
          </div>
          <div className="text-xs text-gray-500 mt-2">
            This session
          </div>
        </div>
      </div>

      {/* Expertise Mini Panel */}
      <ExpertiseMiniPanel
        recentLearnings={recentLearnings}
        domainSummaries={domainSummaries}
        onViewDetails={onViewExpertise}
      />

      {/* Batch Flow */}
      <div className="space-y-2">
        {batches.length === 0 ? (
          <div className="p-8 rounded-lg bg-gray-800/50 border border-gray-700 text-center">
            <Layers className="w-12 h-12 text-gray-600 mx-auto mb-3" />
            <p className="text-gray-400 mb-2">No execution plan</p>
            <p className="text-sm text-gray-500">
              Click "Rebuild" to generate an execution plan from pending tasks
            </p>
          </div>
        ) : (
          batches.map((batch, index) => {
            const sessions = getSessionsForBatch(batch);
            const isCurrentBatch = index === currentBatchIndex && isRunning;
            const showMergePoint = batch.status === 'merging' ||
              (batch.status === 'completed' && batch.taskIds.length > 1);

            return (
              <React.Fragment key={batch.batchId}>
                {/* Connector from previous batch */}
                {index > 0 && (
                  <BatchConnector
                    isComplete={batches[index - 1].status === 'completed'}
                    isActive={batches[index - 1].status === 'running' || batches[index - 1].status === 'merging'}
                    height={32}
                  />
                )}

                {/* Batch Card */}
                <BatchCard
                  batch={batch}
                  sessions={sessions}
                  worktrees={worktrees}
                  isExpanded={expandedBatches.has(batch.batchId)}
                  onToggleExpand={() => toggleBatchExpand(batch.batchId)}
                  onViewSessionDetails={onViewSessionDetails}
                  onStopSession={isCurrentBatch ? (taskId) => {
                    // Could implement individual task stopping
                    console.log('Stop task:', taskId);
                  } : undefined}
                />

                {/* Merge Point */}
                {showMergePoint && pendingMerge && pendingMerge.batchId === batch.batchId && (
                  <MergePoint
                    merge={pendingMerge}
                    onForceMerge={() => {
                      pendingMerge.worktreesToMerge.forEach(wt => {
                        if (wt.status === 'pending' || wt.status === 'conflict') {
                          triggerMerge(wt.id);
                        }
                      });
                    }}
                    className="my-4"
                  />
                )}
              </React.Fragment>
            );
          })
        )}
      </div>

      {/* Task Queue (upcoming batches) */}
      {upcomingBatches.length > 0 && (
        <TaskQueue
          upcomingBatches={upcomingBatches}
          onExpandBatch={(batchId) => toggleBatchExpand(batchId)}
        />
      )}
    </div>
  );
}
