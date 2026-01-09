'use client';

import React, { useState, useEffect } from 'react';
import {
  X,
  ChevronLeft,
  ChevronRight,
  Loader2,
  CheckCircle,
  XCircle,
  Clock,
  Cpu,
  GitBranch,
  Terminal,
  Image as ImageIcon,
  BarChart3,
  DollarSign,
  History,
  FileText,
  AlertCircle,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { api } from '@/lib/api';
import type { SessionInfo, ToolUse } from './hooks/useParallelState';
import type { Screenshot } from '@/lib/types';

interface SessionDetailModalProps {
  isOpen: boolean;
  onClose: () => void;
  session: SessionInfo | null;
  allSessions: SessionInfo[];
  onNavigate: (taskId: number) => void;
  projectId: string;
}

type TabType = 'current' | 'history' | 'logs' | 'screenshots' | 'quality' | 'costs';

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

function formatToolName(name: string): string {
  return name
    .replace(/_/g, ' ')
    .replace(/([A-Z])/g, ' $1')
    .trim()
    .toLowerCase()
    .replace(/^./, s => s.toUpperCase());
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
    case 'failed':
      return 'bg-red-500/20 text-red-400 border-red-500/30';
    default:
      return 'bg-gray-500/20 text-gray-400 border-gray-500/30';
  }
}

export function SessionDetailModal({
  isOpen,
  onClose,
  session,
  allSessions,
  onNavigate,
  projectId,
}: SessionDetailModalProps) {
  const [activeTab, setActiveTab] = useState<TabType>('current');
  const [logs, setLogs] = useState<string>('');
  const [logsLoading, setLogsLoading] = useState(false);
  const [screenshots, setScreenshots] = useState<Screenshot[]>([]);
  const [screenshotsLoading, setScreenshotsLoading] = useState(false);

  // Find prev/next sessions for navigation
  const currentIndex = session ? allSessions.findIndex(s => s.taskId === session.taskId) : -1;
  const prevSession = currentIndex > 0 ? allSessions[currentIndex - 1] : null;
  const nextSession = currentIndex < allSessions.length - 1 ? allSessions[currentIndex + 1] : null;

  // Load logs when logs tab is selected
  useEffect(() => {
    if (isOpen && activeTab === 'logs' && session?.sessionId) {
      loadLogs();
    }
  }, [isOpen, activeTab, session?.sessionId]);

  // Load screenshots when screenshots tab is selected
  useEffect(() => {
    if (isOpen && activeTab === 'screenshots' && session) {
      loadScreenshots();
    }
  }, [isOpen, activeTab, session?.taskId]);

  async function loadLogs() {
    if (!session?.sessionId) return;
    setLogsLoading(true);
    try {
      // Try to load logs for this session
      const logsList = await api.getSessionLogs(projectId);
      // Find log for this session (by session number or task id)
      const humanLog = logsList.find((l: any) =>
        l.filename.includes(`session_${session.taskId}`) ||
        l.session_number === session.taskId
      );
      if (humanLog) {
        const content = await api.getSessionLogContent(projectId, 'human', humanLog.filename);
        setLogs(content);
      } else {
        setLogs('No logs available yet for this session.');
      }
    } catch (err) {
      console.error('Failed to load logs:', err);
      setLogs('Failed to load logs.');
    } finally {
      setLogsLoading(false);
    }
  }

  async function loadScreenshots() {
    if (!session) return;
    setScreenshotsLoading(true);
    try {
      const allScreenshots = await api.listScreenshots(projectId);
      // Filter screenshots for this task
      const taskScreenshots = allScreenshots
        .filter((s: Screenshot) => s.task_id === session.taskId)
        .map((s: Screenshot) => ({
          ...s,
          url: api.getScreenshotUrl(projectId, s.filename)
        }));
      setScreenshots(taskScreenshots);
    } catch (err) {
      console.error('Failed to load screenshots:', err);
    } finally {
      setScreenshotsLoading(false);
    }
  }

  // Reset tab when modal opens
  useEffect(() => {
    if (isOpen) {
      setActiveTab('current');
    }
  }, [isOpen]);

  if (!isOpen || !session) return null;

  const isRunning = session.phase === 'planning' || session.phase === 'executing' || session.phase === 'verifying';
  const progressPercent = session.progress.total > 0
    ? Math.round((session.progress.completed / session.progress.total) * 100)
    : 0;

  const tabs: { id: TabType; label: string; icon: React.ElementType }[] = [
    { id: 'current', label: 'Current', icon: Terminal },
    { id: 'history', label: 'History', icon: History },
    { id: 'logs', label: 'Logs', icon: FileText },
    { id: 'screenshots', label: 'Screenshots', icon: ImageIcon },
    { id: 'quality', label: 'Quality', icon: BarChart3 },
    { id: 'costs', label: 'Costs', icon: DollarSign },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative w-full max-w-4xl max-h-[90vh] bg-gray-900 rounded-lg border border-gray-700 overflow-hidden flex flex-col shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-700 bg-gray-800/50">
          <div className="flex items-center gap-4">
            {/* Navigation arrows */}
            <button
              onClick={() => prevSession && onNavigate(prevSession.taskId)}
              disabled={!prevSession}
              className={cn(
                'p-1.5 rounded-lg transition-colors',
                prevSession
                  ? 'hover:bg-gray-700 text-gray-300'
                  : 'text-gray-600 cursor-not-allowed'
              )}
              title={prevSession ? `Previous: Task #${prevSession.taskId}` : 'No previous session'}
            >
              <ChevronLeft className="w-5 h-5" />
            </button>

            <div>
              <h2 className="text-lg font-semibold text-gray-100">
                {session.epicName} - Task #{session.taskId}
              </h2>
              <p className="text-sm text-gray-400 line-clamp-1">
                {session.taskDescription}
              </p>
            </div>

            <button
              onClick={() => nextSession && onNavigate(nextSession.taskId)}
              disabled={!nextSession}
              className={cn(
                'p-1.5 rounded-lg transition-colors',
                nextSession
                  ? 'hover:bg-gray-700 text-gray-300'
                  : 'text-gray-600 cursor-not-allowed'
              )}
              title={nextSession ? `Next: Task #${nextSession.taskId}` : 'No next session'}
            >
              <ChevronRight className="w-5 h-5" />
            </button>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-gray-700 text-gray-400 hover:text-gray-200 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Status Bar */}
        <div className="flex items-center gap-4 px-4 py-3 bg-gray-800/30 border-b border-gray-700">
          {/* Phase badge */}
          <span className={cn(
            'inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-sm font-medium border',
            getPhaseColor(session.phase)
          )}>
            {isRunning && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            {session.phase === 'completed' && <CheckCircle className="w-3.5 h-3.5" />}
            {session.phase === 'failed' && <XCircle className="w-3.5 h-3.5" />}
            {session.phase}
          </span>

          {/* Model badge */}
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-blue-500/20 text-blue-400 border border-blue-500/30">
            <Cpu className="w-3 h-3" />
            {formatModel(session.model)}
          </span>

          {/* Branch */}
          {session.worktreeBranch && (
            <span className="inline-flex items-center gap-1 text-xs text-gray-400">
              <GitBranch className="w-3 h-3" />
              <span className="font-mono">{session.worktreeBranch}</span>
            </span>
          )}

          {/* Duration */}
          <span className="inline-flex items-center gap-1 text-xs text-gray-400 ml-auto">
            <Clock className="w-3 h-3" />
            {formatDuration(session.duration)}
          </span>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-gray-700 overflow-x-auto">
          {tabs.map(tab => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  'flex items-center gap-2 px-4 py-2.5 text-sm font-medium transition-colors whitespace-nowrap',
                  activeTab === tab.id
                    ? 'text-blue-400 border-b-2 border-blue-400 bg-gray-800/50'
                    : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/30'
                )}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Tab Content */}
        <div className="flex-1 overflow-y-auto p-4">
          {/* CURRENT TAB */}
          {activeTab === 'current' && (
            <div className="space-y-4">
              {/* Progress */}
              <div className="p-4 bg-gray-800/50 rounded-lg border border-gray-700">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-gray-400">Progress</span>
                  <span className="text-sm text-gray-300">
                    {session.progress.completed}/{session.progress.total} steps
                  </span>
                </div>
                <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                  <div
                    className={cn(
                      'h-full rounded-full transition-all duration-500',
                      progressPercent === 100 ? 'bg-green-500' : 'bg-blue-500'
                    )}
                    style={{ width: `${progressPercent}%` }}
                  />
                </div>
              </div>

              {/* Current Tool */}
              {isRunning && session.currentTool && (
                <div className="p-4 bg-yellow-500/10 rounded-lg border border-yellow-500/30">
                  <div className="flex items-center gap-2 mb-2">
                    <Loader2 className="w-4 h-4 text-yellow-400 animate-spin" />
                    <span className="text-sm font-medium text-yellow-400">Currently executing:</span>
                  </div>
                  <span className="text-lg text-yellow-300 font-mono">
                    {formatToolName(session.currentTool)}
                  </span>
                </div>
              )}

              {/* Recent Activity */}
              <div className="p-4 bg-gray-800/50 rounded-lg border border-gray-700">
                <h3 className="text-sm font-medium text-gray-300 mb-3">Recent Activity</h3>
                {session.toolUses && session.toolUses.length > 0 ? (
                  <div className="space-y-2 max-h-64 overflow-y-auto">
                    {session.toolUses.slice().reverse().map((tool, idx) => (
                      <div
                        key={`${tool.id}-${idx}`}
                        className="flex items-center gap-3 py-2 px-3 bg-gray-900/50 rounded border border-gray-700"
                      >
                        <CheckCircle className="w-4 h-4 text-green-500 flex-shrink-0" />
                        <span className="text-sm text-gray-300">{formatToolName(tool.name)}</span>
                        <span className="text-xs text-gray-500 ml-auto">
                          {new Date(tool.timestamp).toLocaleTimeString()}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-gray-500">No activity recorded yet.</p>
                )}
              </div>

              {/* Error message */}
              {session.phase === 'failed' && session.error && (
                <div className="p-4 bg-red-500/10 rounded-lg border border-red-500/30">
                  <div className="flex items-center gap-2 mb-2">
                    <AlertCircle className="w-4 h-4 text-red-400" />
                    <span className="text-sm font-medium text-red-400">Error</span>
                  </div>
                  <p className="text-sm text-red-300 font-mono">{session.error}</p>
                </div>
              )}
            </div>
          )}

          {/* HISTORY TAB */}
          {activeTab === 'history' && (
            <div className="space-y-4">
              <h3 className="text-lg font-medium text-gray-200">Completed Tasks in Epic</h3>
              <p className="text-sm text-gray-400">
                History of completed tasks in the "{session.epicName}" epic.
              </p>
              <div className="p-8 text-center text-gray-500">
                <History className="w-12 h-12 mx-auto mb-3 opacity-50" />
                <p>Task history will be displayed here.</p>
                <p className="text-sm mt-1">Coming soon in a future update.</p>
              </div>
            </div>
          )}

          {/* LOGS TAB */}
          {activeTab === 'logs' && (
            <div className="space-y-4">
              <h3 className="text-lg font-medium text-gray-200">Session Logs</h3>
              {logsLoading ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="w-6 h-6 text-blue-400 animate-spin" />
                  <span className="ml-2 text-gray-400">Loading logs...</span>
                </div>
              ) : (
                <div className="p-4 bg-gray-800/50 rounded-lg border border-gray-700">
                  <pre className="text-sm text-gray-300 font-mono whitespace-pre-wrap max-h-96 overflow-y-auto">
                    {logs || 'No logs available.'}
                  </pre>
                </div>
              )}
            </div>
          )}

          {/* SCREENSHOTS TAB */}
          {activeTab === 'screenshots' && (
            <div className="space-y-4">
              <h3 className="text-lg font-medium text-gray-200">Browser Screenshots</h3>
              {screenshotsLoading ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="w-6 h-6 text-blue-400 animate-spin" />
                  <span className="ml-2 text-gray-400">Loading screenshots...</span>
                </div>
              ) : screenshots.length > 0 ? (
                <div className="grid grid-cols-2 gap-4">
                  {screenshots.map((screenshot) => (
                    <div
                      key={screenshot.filename}
                      className="rounded-lg overflow-hidden border border-gray-700 bg-gray-800/50"
                    >
                      <img
                        src={screenshot.url}
                        alt={screenshot.filename}
                        className="w-full h-48 object-contain bg-gray-900"
                        loading="lazy"
                      />
                      <div className="p-2 text-xs text-gray-400">
                        {screenshot.filename}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="p-8 text-center text-gray-500">
                  <ImageIcon className="w-12 h-12 mx-auto mb-3 opacity-50" />
                  <p>No screenshots for this task.</p>
                </div>
              )}
            </div>
          )}

          {/* QUALITY TAB */}
          {activeTab === 'quality' && (
            <div className="space-y-4">
              <h3 className="text-lg font-medium text-gray-200">Quality Metrics</h3>
              <div className="p-8 text-center text-gray-500">
                <BarChart3 className="w-12 h-12 mx-auto mb-3 opacity-50" />
                <p>Quality metrics will be displayed here.</p>
                <p className="text-sm mt-1">Coming soon in a future update.</p>
              </div>
            </div>
          )}

          {/* COSTS TAB */}
          {activeTab === 'costs' && (
            <div className="space-y-4">
              <h3 className="text-lg font-medium text-gray-200">Cost Breakdown</h3>
              <div className="p-8 text-center text-gray-500">
                <DollarSign className="w-12 h-12 mx-auto mb-3 opacity-50" />
                <p>Cost information will be displayed here.</p>
                <p className="text-sm mt-1">Coming soon in a future update.</p>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-4 py-3 border-t border-gray-700 bg-gray-800/30">
          <span className="text-xs text-gray-500">
            Session {currentIndex + 1} of {allSessions.length}
          </span>
          <button
            onClick={onClose}
            className="px-4 py-1.5 text-sm bg-gray-700 hover:bg-gray-600 text-gray-200 rounded-lg transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
