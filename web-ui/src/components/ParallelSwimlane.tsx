/**
 * ParallelSwimlane - Swimlane visualization for parallel task execution
 *
 * Features:
 * - Display parallel task execution as swimlane diagram
 * - Column per epic (horizontal lanes)
 * - Tasks as cards within lanes
 * - Real-time status coloring: gray (pending), blue (running), green (complete), red (error)
 * - Dependency arrows between related tasks
 * - Zoom and pan for large projects
 */

'use client';

import React, { useState, useRef, useEffect } from 'react';
import {
  CheckCircle,
  Circle,
  XCircle,
  Loader2,
  ZoomIn,
  ZoomOut,
  Maximize2
} from 'lucide-react';
import type { Epic, Task } from '@/lib/types';

interface TaskWithDependencies extends Task {
  depends_on?: number[];
  status?: 'pending' | 'running' | 'completed' | 'error';
}

interface ParallelSwimlaneProps {
  epics: Epic[];
  tasks: TaskWithDependencies[];
  className?: string;
}

// Task status color mapping
const getTaskColor = (status: string | undefined, done: boolean) => {
  if (done) return 'bg-green-500/20 border-green-500/50 text-green-400';
  if (status === 'error') return 'bg-red-500/20 border-red-500/50 text-red-400';
  if (status === 'running') return 'bg-blue-500/20 border-blue-500/50 text-blue-400';
  return 'bg-gray-500/20 border-gray-500/50 text-gray-400';
};

const getStatusIcon = (status: string | undefined, done: boolean) => {
  if (done) return <CheckCircle className="w-4 h-4 text-green-400" />;
  if (status === 'error') return <XCircle className="w-4 h-4 text-red-400" />;
  if (status === 'running') return <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />;
  return <Circle className="w-4 h-4 text-gray-400" />;
};

export function ParallelSwimlane({ epics, tasks, className = '' }: ParallelSwimlaneProps) {
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  // Group tasks by epic
  const tasksByEpic = tasks.reduce((acc, task) => {
    if (!acc[task.epic_id]) {
      acc[task.epic_id] = [];
    }
    acc[task.epic_id].push(task);
    return acc;
  }, {} as Record<number, TaskWithDependencies[]>);

  // Handle zoom
  const handleZoomIn = () => setZoom(prev => Math.min(prev + 0.2, 2));
  const handleZoomOut = () => setZoom(prev => Math.max(prev - 0.2, 0.5));
  const handleResetZoom = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  // Handle panning
  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button === 0) { // Left click only
      setIsDragging(true);
      setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
    }
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isDragging) {
      setPan({
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y,
      });
    }
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  // Calculate task card positions for dependency arrows
  const [taskPositions, setTaskPositions] = useState<Record<number, { x: number; y: number; width: number; height: number }>>({});

  useEffect(() => {
    // Calculate positions after render
    const positions: Record<number, { x: number; y: number; width: number; height: number }> = {};

    epics.forEach((epic, epicIndex) => {
      const epicTasks = tasksByEpic[epic.id] || [];
      epicTasks.forEach((task, taskIndex) => {
        const card = document.getElementById(`task-card-${task.id}`);
        if (card) {
          const rect = card.getBoundingClientRect();
          const container = containerRef.current?.getBoundingClientRect();
          if (container) {
            positions[task.id] = {
              x: rect.left - container.left + rect.width / 2,
              y: rect.top - container.top + rect.height / 2,
              width: rect.width,
              height: rect.height,
            };
          }
        }
      });
    });

    setTaskPositions(positions);
  }, [epics, tasks, tasksByEpic, zoom, pan]);

  // Generate dependency arrows
  const renderDependencyArrows = () => {
    const arrows: JSX.Element[] = [];

    tasks.forEach(task => {
      if (task.depends_on && task.depends_on.length > 0) {
        task.depends_on.forEach(depId => {
          const fromPos = taskPositions[depId];
          const toPos = taskPositions[task.id];

          if (fromPos && toPos) {
            // Draw arrow from dependency to task
            const arrowId = `arrow-${depId}-${task.id}`;
            arrows.push(
              <g key={arrowId}>
                {/* Arrow line */}
                <line
                  x1={fromPos.x}
                  y1={fromPos.y}
                  x2={toPos.x}
                  y2={toPos.y}
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeDasharray="4 4"
                  className="text-gray-600"
                  markerEnd="url(#arrowhead)"
                />
              </g>
            );
          }
        });
      }
    });

    return arrows;
  };

  return (
    <div className={`relative ${className}`}>
      {/* Zoom Controls */}
      <div className="absolute top-4 right-4 z-10 flex gap-2">
        <button
          onClick={handleZoomIn}
          className="p-2 bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded-lg transition-colors"
          title="Zoom In"
        >
          <ZoomIn className="w-4 h-4 text-gray-300" />
        </button>
        <button
          onClick={handleZoomOut}
          className="p-2 bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded-lg transition-colors"
          title="Zoom Out"
        >
          <ZoomOut className="w-4 h-4 text-gray-300" />
        </button>
        <button
          onClick={handleResetZoom}
          className="p-2 bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded-lg transition-colors"
          title="Reset View"
        >
          <Maximize2 className="w-4 h-4 text-gray-300" />
        </button>
      </div>

      {/* Swimlane Container */}
      <div
        ref={containerRef}
        className="relative overflow-auto bg-gray-950 border border-gray-800 rounded-lg"
        style={{ height: '600px', cursor: isDragging ? 'grabbing' : 'grab' }}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        {/* Content with zoom and pan */}
        <div
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            transformOrigin: '0 0',
            transition: isDragging ? 'none' : 'transform 0.1s ease-out',
            minWidth: `${epics.length * 320}px`,
            minHeight: '100%',
          }}
        >
          {/* Epic Lanes */}
          <div className="flex gap-4 p-6">
            {epics.map((epic, epicIndex) => {
              const epicTasks = tasksByEpic[epic.id] || [];
              const completedCount = epicTasks.filter(t => t.done).length;
              const totalCount = epicTasks.length;

              return (
                <div
                  key={epic.id}
                  className="flex-shrink-0"
                  style={{ width: '300px' }}
                >
                  {/* Epic Header */}
                  <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 mb-4">
                    <h3 className="text-sm font-semibold text-gray-100 mb-2 truncate" title={epic.name}>
                      {epic.name}
                    </h3>
                    <div className="flex items-center gap-2 text-xs text-gray-400">
                      <span>{completedCount}/{totalCount} tasks</span>
                      {completedCount === totalCount && totalCount > 0 && (
                        <CheckCircle className="w-3 h-3 text-green-400" />
                      )}
                    </div>
                  </div>

                  {/* Task Cards */}
                  <div className="space-y-3">
                    {epicTasks.length === 0 ? (
                      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 text-center">
                        <p className="text-xs text-gray-500">No tasks</p>
                      </div>
                    ) : (
                      epicTasks.map((task, taskIndex) => (
                        <div
                          key={task.id}
                          id={`task-card-${task.id}`}
                          className={`border rounded-lg p-3 transition-all ${getTaskColor(task.status, task.done)}`}
                        >
                          {/* Task Header */}
                          <div className="flex items-start gap-2 mb-2">
                            {getStatusIcon(task.status, task.done)}
                            <span className="text-xs font-medium flex-1 leading-tight">
                              Task #{task.id}
                            </span>
                          </div>

                          {/* Task Description */}
                          <p className="text-xs text-gray-300 mb-2 line-clamp-2">
                            {task.description}
                          </p>

                          {/* Task Metadata */}
                          <div className="flex items-center justify-between text-xs text-gray-500">
                            <span>Priority: {task.priority}</span>
                            {task.depends_on && task.depends_on.length > 0 && (
                              <span className="text-blue-400" title={`Depends on: ${task.depends_on.join(', ')}`}>
                                {task.depends_on.length} dep{task.depends_on.length > 1 ? 's' : ''}
                              </span>
                            )}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* SVG Overlay for Dependency Arrows */}
          <svg
            ref={svgRef}
            className="absolute top-0 left-0 pointer-events-none"
            style={{ width: '100%', height: '100%' }}
          >
            {/* Arrow marker definition */}
            <defs>
              <marker
                id="arrowhead"
                markerWidth="10"
                markerHeight="10"
                refX="9"
                refY="3"
                orient="auto"
                className="text-gray-600"
              >
                <polygon points="0 0, 10 3, 0 6" fill="currentColor" />
              </marker>
            </defs>

            {/* Render arrows */}
            {renderDependencyArrows()}
          </svg>
        </div>
      </div>

      {/* Legend */}
      <div className="mt-4 flex items-center gap-6 text-xs text-gray-400">
        <div className="flex items-center gap-2">
          <Circle className="w-3 h-3 text-gray-400" />
          <span>Pending</span>
        </div>
        <div className="flex items-center gap-2">
          <Loader2 className="w-3 h-3 text-blue-400" />
          <span>Running</span>
        </div>
        <div className="flex items-center gap-2">
          <CheckCircle className="w-3 h-3 text-green-400" />
          <span>Completed</span>
        </div>
        <div className="flex items-center gap-2">
          <XCircle className="w-3 h-3 text-red-400" />
          <span>Error</span>
        </div>
        <div className="flex items-center gap-2 ml-4">
          <div className="w-6 h-0 border-t-2 border-dashed border-gray-600" />
          <span>Dependencies</span>
        </div>
      </div>
    </div>
  );
}
