'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { api } from '@/lib/api';

// Types
export interface ToolUse {
  name: string;
  id: string;
  timestamp: Date;
}

export interface SessionInfo {
  taskId: number;
  sessionId: string;
  epicId: number;
  epicName: string;
  taskDescription: string;
  worktreeBranch: string;
  phase: 'planning' | 'executing' | 'verifying' | 'completed' | 'failed';
  progress: { completed: number; total: number };
  duration: number;
  model: string;
  startedAt: Date;
  // Streaming output tracking
  toolUses?: ToolUse[];
  currentTool?: string;
  error?: string;
}

export interface BatchState {
  batchId: number;
  status: 'queued' | 'running' | 'merging' | 'completed' | 'failed';
  taskIds: number[];
  canParallel: boolean;
  dependsOn: number[];
  startedAt?: Date;
  completedAt?: Date;
  mergeStatus?: 'pending' | 'success' | 'conflict';
}

export interface WorktreeInfo {
  id: string;
  epicId: number;
  branch: string;
  path: string;
  status: 'active' | 'merged' | 'conflict' | 'pending';
  createdAt: Date;
  mergedAt?: Date;
}

export interface MergeInfo {
  batchId: number;
  worktreesToMerge: WorktreeInfo[];
  completedCount: number;
  totalCount: number;
  agent: string;
}

export interface ExecutionPlan {
  projectId: string;
  batches: Array<{
    batch_id: number;
    task_ids: number[];
    can_parallel: boolean;
    depends_on: number[];
  }>;
  worktreeAssignments: Record<number, string>;
  metadata: {
    total_tasks: number;
    total_batches: number;
    parallel_possible: number;
  };
}

export interface LearningEvent {
  taskId: number;
  domain: string;
  patternsLearned: number;
  timestamp: Date;
}

export interface DomainSummary {
  domain: string;
  patternCount: number;
  techniqueCount: number;
  lastUpdated: Date;
}

export interface ParallelState {
  // Execution state
  isRunning: boolean;
  isPaused: boolean;
  executionPlan: ExecutionPlan | null;

  // Batch tracking
  currentBatchIndex: number;
  batches: BatchState[];

  // Running tasks
  runningSessions: Map<number, SessionInfo>;

  // Worktrees
  worktrees: WorktreeInfo[];

  // Merge state
  pendingMerge: MergeInfo | null;

  // Expertise
  recentLearnings: LearningEvent[];
  domainSummaries: DomainSummary[];

  // Costs
  totalCost: number;
}

interface UseParallelStateOptions {
  projectId: string;
  onSessionStart?: (session: SessionInfo) => void;
  onSessionComplete?: (taskId: number) => void;
  onBatchComplete?: (batchId: number) => void;
  onExpertiseLearned?: (event: LearningEvent) => void;
}

export function useParallelState(options: UseParallelStateOptions) {
  const { projectId, onSessionStart, onSessionComplete, onBatchComplete, onExpertiseLearned } = options;

  // State
  const [isRunning, setIsRunning] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [executionPlan, setExecutionPlan] = useState<ExecutionPlan | null>(null);
  const [currentBatchIndex, setCurrentBatchIndex] = useState(0);
  const [batches, setBatches] = useState<BatchState[]>([]);
  const [runningSessions, setRunningSessions] = useState<Map<number, SessionInfo>>(new Map());
  const [worktrees, setWorktrees] = useState<WorktreeInfo[]>([]);
  const [pendingMerge, setPendingMerge] = useState<MergeInfo | null>(null);
  const [recentLearnings, setRecentLearnings] = useState<LearningEvent[]>([]);
  const [domainSummaries, setDomainSummaries] = useState<DomainSummary[]>([]);
  const [totalCost, setTotalCost] = useState(0);

  // Rebuild progress state
  const [isRebuilding, setIsRebuilding] = useState(false);
  const [rebuildProgress, setRebuildProgress] = useState(0);
  const [rebuildStep, setRebuildStep] = useState<string | null>(null);
  const [rebuildDetail, setRebuildDetail] = useState<string | null>(null);

  // Refs for intervals
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const durationIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Load initial data
  const loadParallelStatus = useCallback(async () => {
    try {
      const status = await api.getParallelStatus(projectId);

      setIsRunning(status.is_running || false);
      setIsPaused(status.is_paused || false);
      setTotalCost(status.total_cost || 0);

      if (status.execution_plan) {
        setExecutionPlan(status.execution_plan);

        // Convert plan batches to BatchState, using actual status from database
        const batchStatuses = status.batch_statuses || {};
        const batchStates: BatchState[] = status.execution_plan.batches.map((b: any, idx: number) => {
          // Get actual status from database if available
          const dbStatus = batchStatuses[b.batch_id] || batchStatuses[idx];
          const actualStatus = dbStatus?.status || (
            idx < (status.current_batch || 0) ? 'completed' :
            idx === (status.current_batch || 0) && status.is_running ? 'running' : 'queued'
          );

          return {
            batchId: b.batch_id,
            status: actualStatus as BatchState['status'],
            taskIds: b.task_ids,
            canParallel: b.can_parallel,
            dependsOn: b.depends_on || [],
            startedAt: dbStatus?.started_at ? new Date(dbStatus.started_at) : undefined,
            completedAt: dbStatus?.completed_at ? new Date(dbStatus.completed_at) : undefined,
          };
        });
        setBatches(batchStates);
        setCurrentBatchIndex(status.current_batch || 0);
      }

      // Load running agents
      if (status.running_agents && Array.isArray(status.running_agents)) {
        const sessions = new Map<number, SessionInfo>();
        for (const agent of status.running_agents) {
          sessions.set(agent.task_id, {
            taskId: agent.task_id,
            sessionId: agent.session_id || '',
            epicId: agent.epic_id || 0,
            epicName: agent.epic_name || '',
            taskDescription: agent.task_name || agent.task_description || '',
            worktreeBranch: agent.worktree || '',
            phase: agent.phase || 'executing',
            progress: { completed: agent.progress?.completed || 0, total: agent.progress?.total || 5 },
            duration: agent.duration || 0,
            model: agent.model || 'sonnet',
            startedAt: agent.started_at ? new Date(agent.started_at) : new Date(),
          });
        }
        setRunningSessions(sessions);
      }
    } catch (err) {
      console.error('Failed to load parallel status:', err);
    }
  }, [projectId]);

  // Load worktrees
  const loadWorktrees = useCallback(async () => {
    try {
      const data = await api.getWorktrees(projectId);
      if (Array.isArray(data)) {
        setWorktrees(data.map((w: any) => ({
          id: w.id,
          epicId: w.epic_id,
          branch: w.branch_name || w.branch,
          path: w.worktree_path || w.path,
          status: w.status || 'pending',
          createdAt: new Date(w.created_at),
          mergedAt: w.merged_at ? new Date(w.merged_at) : undefined,
        })));
      }
    } catch (err) {
      console.error('Failed to load worktrees:', err);
    }
  }, [projectId]);

  // Load expertise summaries
  const loadExpertise = useCallback(async () => {
    try {
      const data = await api.getExpertiseDomains(projectId);
      if (Array.isArray(data)) {
        setDomainSummaries(data.map((d: any) => ({
          domain: d.domain,
          patternCount: d.pattern_count || d.learning_count || 0,
          techniqueCount: d.technique_count || 0,
          lastUpdated: d.updated_at ? new Date(d.updated_at) : new Date(),
        })));
      }
    } catch (err) {
      // Expertise endpoint may not exist yet
      console.debug('Failed to load expertise:', err);
    }
  }, [projectId]);

  // Update session duration every second
  useEffect(() => {
    if (isRunning && runningSessions.size > 0) {
      durationIntervalRef.current = setInterval(() => {
        setRunningSessions(prev => {
          const updated = new Map(prev);
          for (const [taskId, session] of updated) {
            const elapsed = Math.floor((Date.now() - session.startedAt.getTime()) / 1000);
            updated.set(taskId, { ...session, duration: elapsed });
          }
          return updated;
        });
      }, 1000);
    }

    return () => {
      if (durationIntervalRef.current) {
        clearInterval(durationIntervalRef.current);
      }
    };
  }, [isRunning, runningSessions.size]);

  // Poll for status when running
  useEffect(() => {
    loadParallelStatus();
    loadWorktrees();
    loadExpertise();

    if (isRunning) {
      pollIntervalRef.current = setInterval(() => {
        loadParallelStatus();
        loadWorktrees();
      }, 5000);
    }

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, [isRunning, loadParallelStatus, loadWorktrees, loadExpertise]);

  // Handle WebSocket events
  const handleWebSocketMessage = useCallback((message: any) => {
    switch (message.type) {
      case 'batch_start':
        setBatches(prev => prev.map(b =>
          b.batchId === message.batch_id
            ? { ...b, status: 'running', startedAt: new Date() }
            : b
        ));
        setCurrentBatchIndex(message.batch_index || 0);
        break;

      case 'agent_start':
      case 'task_start':
        const newSession: SessionInfo = {
          taskId: message.task_id,
          sessionId: message.session_id || '',
          epicId: message.epic_id || 0,
          epicName: message.epic_name || '',
          taskDescription: message.task_description || '',
          worktreeBranch: message.worktree || '',
          phase: 'planning',
          progress: { completed: 0, total: 5 },
          duration: 0,
          model: message.model || 'sonnet',
          startedAt: new Date(),
          toolUses: [],  // Initialize streaming output
          currentTool: undefined,
        };
        setRunningSessions(prev => new Map(prev).set(message.task_id, newSession));
        onSessionStart?.(newSession);
        break;

      case 'agent_complete':
        setRunningSessions(prev => {
          const updated = new Map(prev);
          const session = updated.get(message.task_id);
          if (session) {
            updated.set(message.task_id, {
              ...session,
              phase: message.success ? 'completed' : 'failed',
              duration: message.duration || 0,
              error: message.error,
            });
          }
          return updated;
        });
        // Remove from running after short delay to show completion
        setTimeout(() => {
          setRunningSessions(prev => {
            const updated = new Map(prev);
            updated.delete(message.task_id);
            return updated;
          });
        }, 3000);
        break;

      case 'tool_use':
        // Update session with current tool being used
        if (message.task_id !== undefined) {
          setRunningSessions(prev => {
            const updated = new Map(prev);
            const session = updated.get(message.task_id);
            if (session) {
              const toolUses = session.toolUses || [];
              updated.set(message.task_id, {
                ...session,
                phase: 'executing',
                currentTool: message.tool_name,
                toolUses: [...toolUses, { name: message.tool_name, id: message.tool_id, timestamp: new Date() }],
              });
            }
            return updated;
          });
        }
        break;

      case 'tool_result':
        // Tool completed - could update UI to show result
        if (message.task_id !== undefined) {
          setRunningSessions(prev => {
            const updated = new Map(prev);
            const session = updated.get(message.task_id);
            if (session) {
              updated.set(message.task_id, {
                ...session,
                currentTool: undefined,  // Clear current tool
                progress: {
                  completed: (session.progress?.completed || 0) + 1,
                  total: session.progress?.total || 10
                },
              });
            }
            return updated;
          });
        }
        break;

      case 'task_progress':
        setRunningSessions(prev => {
          const updated = new Map(prev);
          const session = updated.get(message.task_id);
          if (session) {
            updated.set(message.task_id, {
              ...session,
              phase: message.phase || session.phase,
              progress: message.progress || session.progress,
            });
          }
          return updated;
        });
        break;

      case 'task_complete':
        setRunningSessions(prev => {
          const updated = new Map(prev);
          updated.delete(message.task_id);
          return updated;
        });
        setTotalCost(prev => prev + (message.cost || 0));
        onSessionComplete?.(message.task_id);
        break;

      case 'batch_completed':
        setBatches(prev => prev.map(b =>
          b.batchId === message.batch_id
            ? {
                ...b,
                status: message.success ? 'completed' : 'failed',
                completedAt: new Date(),
                mergeStatus: message.merge_status,
              }
            : b
        ));
        onBatchComplete?.(message.batch_id);
        break;

      case 'merge_start':
        setPendingMerge({
          batchId: message.batch_id,
          worktreesToMerge: message.worktrees || [],
          completedCount: 0,
          totalCount: message.total || 0,
          agent: message.agent || 'sonnet',
        });
        break;

      case 'merge_complete':
        setPendingMerge(null);
        loadWorktrees();
        break;

      case 'parallel_complete':
        setIsRunning(false);
        setRunningSessions(new Map());
        break;

      case 'expertise_learned':
        const learningEvent: LearningEvent = {
          taskId: message.task_id,
          domain: message.domain,
          patternsLearned: message.patterns_learned || 0,
          timestamp: new Date(),
        };
        setRecentLearnings(prev => [learningEvent, ...prev].slice(0, 20));
        loadExpertise();
        onExpertiseLearned?.(learningEvent);
        break;

      case 'cost_update':
        setTotalCost(message.cumulative_cost || 0);
        break;

      case 'execution_plan_progress':
        // Rebuild progress streaming
        setIsRebuilding(true);
        setRebuildProgress(message.data?.progress || 0);
        setRebuildStep(message.data?.step || null);
        setRebuildDetail(message.data?.detail || null);
        break;

      case 'execution_plan_ready':
        // Rebuild complete
        setIsRebuilding(false);
        setRebuildProgress(1);
        setRebuildStep(null);
        setRebuildDetail(null);
        loadParallelStatus();
        break;

      case 'execution_plan_error':
        // Rebuild failed
        setIsRebuilding(false);
        setRebuildProgress(0);
        setRebuildStep('error');
        setRebuildDetail(message.data?.error || message.error || 'Build failed');
        break;
    }
  }, [onSessionStart, onSessionComplete, onBatchComplete, onExpertiseLearned, loadWorktrees, loadExpertise, loadParallelStatus]);

  // Actions
  const startExecution = useCallback(async () => {
    try {
      await api.startParallelExecution(projectId);
      setIsRunning(true);
      setIsPaused(false);
      await loadParallelStatus();
    } catch (err) {
      console.error('Failed to start parallel execution:', err);
      throw err;
    }
  }, [projectId, loadParallelStatus]);

  const stopExecution = useCallback(async () => {
    try {
      await api.cancelParallelExecution(projectId);
      setIsRunning(false);
      setRunningSessions(new Map());
    } catch (err) {
      console.error('Failed to stop parallel execution:', err);
      throw err;
    }
  }, [projectId]);

  const pauseExecution = useCallback(async () => {
    try {
      await api.pauseParallelExecution(projectId);
      setIsPaused(true);
    } catch (err) {
      console.error('Failed to pause parallel execution:', err);
      throw err;
    }
  }, [projectId]);

  const resumeExecution = useCallback(async () => {
    try {
      await api.resumeParallelExecution(projectId);
      setIsPaused(false);
    } catch (err) {
      console.error('Failed to resume parallel execution:', err);
      throw err;
    }
  }, [projectId]);

  const rebuildPlan = useCallback(async () => {
    try {
      // Set initial rebuild state (WebSocket will update progress)
      setIsRebuilding(true);
      setRebuildProgress(0);
      setRebuildStep('starting');
      setRebuildDetail('Initiating rebuild...');
      await api.rebuildExecutionPlan(projectId);
      // Note: loadParallelStatus will be called by execution_plan_ready handler
    } catch (err) {
      console.error('Failed to rebuild execution plan:', err);
      setIsRebuilding(false);
      setRebuildStep(null);
      setRebuildDetail(err instanceof Error ? err.message : 'Build failed');
      throw err;
    }
  }, [projectId]);

  const triggerMerge = useCallback(async (worktreeId: string) => {
    try {
      await api.mergeWorktree(worktreeId);
      await loadWorktrees();
    } catch (err) {
      console.error('Failed to merge worktree:', err);
      throw err;
    }
  }, [loadWorktrees]);

  return {
    // State
    isRunning,
    isPaused,
    executionPlan,
    currentBatchIndex,
    batches,
    runningSessions: Array.from(runningSessions.values()),
    worktrees,
    pendingMerge,
    recentLearnings,
    domainSummaries,
    totalCost,

    // Rebuild progress state
    isRebuilding,
    rebuildProgress,
    rebuildStep,
    rebuildDetail,

    // Actions
    startExecution,
    stopExecution,
    pauseExecution,
    resumeExecution,
    rebuildPlan,
    triggerMerge,
    refresh: loadParallelStatus,

    // WebSocket handler
    handleWebSocketMessage,
  };
}
