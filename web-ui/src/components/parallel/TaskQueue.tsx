'use client';

import React, { useState } from 'react';
import {
  ChevronDown,
  ChevronRight,
  Clock,
  Layers,
  ListOrdered,
  ArrowRight,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type { BatchState } from './hooks/useParallelState';

interface TaskQueueProps {
  upcomingBatches: BatchState[];
  onExpandBatch?: (batchId: number) => void;
  className?: string;
}

export function TaskQueue({
  upcomingBatches,
  onExpandBatch,
  className,
}: TaskQueueProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [expandedBatchId, setExpandedBatchId] = useState<number | null>(null);

  const totalQueuedTasks = upcomingBatches.reduce(
    (sum, batch) => sum + batch.taskIds.length,
    0
  );

  if (upcomingBatches.length === 0) {
    return null;
  }

  return (
    <div
      className={cn(
        'rounded-lg border border-gray-700 bg-gray-800/50 backdrop-blur-sm',
        className
      )}
    >
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full p-4 flex items-center justify-between hover:bg-gray-700/30 transition-colors rounded-lg"
      >
        <div className="flex items-center gap-3">
          {isExpanded ? (
            <ChevronDown className="w-5 h-5 text-gray-400" />
          ) : (
            <ChevronRight className="w-5 h-5 text-gray-400" />
          )}

          <ListOrdered className="w-5 h-5 text-gray-400" />
          <span className="font-semibold text-gray-100">
            Task Queue
          </span>

          <span className="text-sm text-gray-400">
            {upcomingBatches.length} batches • {totalQueuedTasks} tasks
          </span>
        </div>

        <div className="flex items-center gap-2 text-xs text-gray-500">
          <Clock className="w-4 h-4" />
          Waiting for current batch
        </div>
      </button>

      {/* Expanded Queue View */}
      {isExpanded && (
        <div className="px-4 pb-4 space-y-3">
          {upcomingBatches.map((batch, index) => {
            const isBatchExpanded = expandedBatchId === batch.batchId;

            return (
              <div
                key={batch.batchId}
                className="rounded-lg border border-gray-700 bg-gray-900/50 overflow-hidden"
              >
                {/* Batch Header */}
                <button
                  onClick={() => {
                    setExpandedBatchId(isBatchExpanded ? null : batch.batchId);
                    onExpandBatch?.(batch.batchId);
                  }}
                  className="w-full p-3 flex items-center justify-between hover:bg-gray-700/30 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    {isBatchExpanded ? (
                      <ChevronDown className="w-4 h-4 text-gray-500" />
                    ) : (
                      <ChevronRight className="w-4 h-4 text-gray-500" />
                    )}

                    <Layers className="w-4 h-4 text-gray-500" />
                    <span className="text-sm font-medium text-gray-200">
                      Batch {batch.batchId}
                    </span>

                    {/* Task count badge */}
                    <span className="px-2 py-0.5 rounded text-xs bg-gray-700 text-gray-300">
                      {batch.taskIds.length} task{batch.taskIds.length !== 1 ? 's' : ''}
                    </span>

                    {/* Parallel indicator */}
                    {batch.canParallel && batch.taskIds.length > 1 && (
                      <span className="px-2 py-0.5 rounded text-xs bg-purple-500/20 text-purple-400 border border-purple-500/30">
                        Parallel
                      </span>
                    )}
                  </div>

                  {/* Dependencies */}
                  {batch.dependsOn.length > 0 && (
                    <div className="flex items-center gap-2 text-xs text-gray-500">
                      <ArrowRight className="w-3 h-3" />
                      <span>After Batch {batch.dependsOn.join(', ')}</span>
                    </div>
                  )}
                </button>

                {/* Expanded Task List */}
                {isBatchExpanded && (
                  <div className="p-3 pt-0 border-t border-gray-700/50">
                    <p className="text-xs text-gray-500 mb-2">
                      Tasks in this batch:
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {batch.taskIds.map(taskId => (
                        <span
                          key={taskId}
                          className="px-2 py-1 rounded bg-gray-800 border border-gray-700 text-xs text-gray-300"
                        >
                          Task #{taskId}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          })}

          {/* Queue Order Indicator */}
          <div className="flex items-center justify-center gap-2 pt-2 text-xs text-gray-500">
            <span>Execution order:</span>
            <div className="flex items-center gap-1">
              {upcomingBatches.map((batch, i) => (
                <React.Fragment key={batch.batchId}>
                  <span className="px-1.5 py-0.5 rounded bg-gray-700 text-gray-400">
                    B{batch.batchId}
                  </span>
                  {i < upcomingBatches.length - 1 && (
                    <ArrowRight className="w-3 h-3 text-gray-600" />
                  )}
                </React.Fragment>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
