/**
 * CostDashboard - Cost tracking and budget management
 *
 * Features:
 * - Real-time cost tracking with live updates
 * - Budget usage progress bar with warning colors
 * - Model usage breakdown pie chart
 * - Cost trend line chart over time
 * - Table of recent costs by session/task
 * - Export cost report functionality
 */

'use client';

import React, { useState } from 'react';
import {
  DollarSign,
  TrendingUp,
  Download,
  AlertTriangle,
  PieChart,
  BarChart3,
  Calendar,
  Filter
} from 'lucide-react';
import { ProgressBar } from './ProgressBar';

interface ModelCost {
  model: string;
  total_cost: number;
  request_count: number;
  percentage: number;
}

interface CostEntry {
  session_id: string;
  task_id?: number;
  task_description?: string;
  model: string;
  cost: number;
  timestamp: string;
  duration?: number;
}

interface TrendDataPoint {
  date: string;
  cost: number;
  cumulative_cost: number;
}

interface CostDashboardProps {
  totalCost: number;
  budget?: number;
  modelBreakdown: ModelCost[];
  recentCosts: CostEntry[];
  trendData: TrendDataPoint[];
  onExport?: () => void;
  className?: string;
}

export function CostDashboard({
  totalCost,
  budget,
  modelBreakdown,
  recentCosts,
  trendData,
  onExport,
  className = '',
}: CostDashboardProps) {
  const [timeFilter, setTimeFilter] = useState<'day' | 'week' | 'month' | 'all'>('week');

  // Calculate budget usage
  const budgetUsage = budget ? (totalCost / budget) * 100 : 0;
  const budgetRemaining = budget ? budget - totalCost : 0;

  // Determine warning level
  const getWarningLevel = () => {
    if (!budget) return 'normal';
    if (budgetUsage >= 90) return 'critical';
    if (budgetUsage >= 75) return 'warning';
    return 'normal';
  };

  const warningLevel = getWarningLevel();

  const getBudgetColor = () => {
    switch (warningLevel) {
      case 'critical':
        return 'red';
      case 'warning':
        return 'yellow';
      default:
        return 'green';
    }
  };

  // Format currency
  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 4,
    }).format(amount);
  };

  // Format date
  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleString();
  };

  // Simple pie chart colors
  const pieColors = [
    'rgb(59, 130, 246)', // blue
    'rgb(34, 197, 94)', // green
    'rgb(168, 85, 247)', // purple
    'rgb(251, 146, 60)', // orange
    'rgb(236, 72, 153)', // pink
  ];

  // Calculate pie chart segments
  const totalAngle = 360;
  let currentAngle = 0;

  const pieSegments = modelBreakdown.map((model, index) => {
    const angle = (model.percentage / 100) * totalAngle;
    const startAngle = currentAngle;
    currentAngle += angle;

    return {
      ...model,
      color: pieColors[index % pieColors.length],
      startAngle,
      endAngle: currentAngle,
    };
  });

  // Export functionality
  const handleExport = () => {
    if (onExport) {
      onExport();
    } else {
      // Default CSV export
      const csv = [
        ['Session ID', 'Task ID', 'Description', 'Model', 'Cost', 'Timestamp', 'Duration (s)'],
        ...recentCosts.map((entry) => [
          entry.session_id,
          entry.task_id || '',
          entry.task_description || '',
          entry.model,
          entry.cost.toString(),
          entry.timestamp,
          entry.duration?.toString() || '',
        ]),
      ]
        .map((row) => row.join(','))
        .join('\n');

      const blob = new Blob([csv], { type: 'text/csv' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `cost-report-${new Date().toISOString()}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    }
  };

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-100 flex items-center gap-2">
          <DollarSign className="w-5 h-5 text-green-400" />
          Cost Dashboard
        </h3>
        <button
          onClick={handleExport}
          className="flex items-center gap-2 px-3 py-1.5 bg-blue-500/20 hover:bg-blue-500/30 text-blue-400 rounded-lg transition-colors text-sm"
        >
          <Download className="w-4 h-4" />
          Export Report
        </button>
      </div>

      {/* Total Cost & Budget */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Total Cost */}
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <DollarSign className="w-4 h-4 text-green-400" />
            <span className="text-sm font-medium text-gray-100">Total Cost</span>
          </div>
          <div className="text-3xl font-bold text-green-400">{formatCurrency(totalCost)}</div>
          {budget && (
            <p className="text-xs text-gray-500 mt-2">
              Budget: {formatCurrency(budget)} ({budgetUsage.toFixed(1)}% used)
            </p>
          )}
        </div>

        {/* Budget Remaining */}
        {budget && (
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle
                className={`w-4 h-4 ${
                  warningLevel === 'critical'
                    ? 'text-red-400'
                    : warningLevel === 'warning'
                    ? 'text-yellow-400'
                    : 'text-gray-400'
                }`}
              />
              <span className="text-sm font-medium text-gray-100">Budget Remaining</span>
            </div>
            <div
              className={`text-3xl font-bold ${
                warningLevel === 'critical'
                  ? 'text-red-400'
                  : warningLevel === 'warning'
                  ? 'text-yellow-400'
                  : 'text-green-400'
              }`}
            >
              {formatCurrency(budgetRemaining)}
            </div>
            <ProgressBar
              value={budgetUsage}
              color={getBudgetColor()}
              className="mt-3"
              showPercentage={false}
            />
          </div>
        )}
      </div>

      {/* Model Breakdown */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <div className="flex items-center gap-2 mb-4">
          <PieChart className="w-4 h-4 text-blue-400" />
          <span className="text-sm font-medium text-gray-100">Model Usage Breakdown</span>
        </div>

        {modelBreakdown.length === 0 ? (
          <p className="text-center text-gray-500 py-8">No usage data yet</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Simple Pie Chart Visualization */}
            <div className="flex items-center justify-center">
              <div className="relative w-48 h-48">
                {pieSegments.map((segment, index) => {
                  const radius = 80;
                  const centerX = 96;
                  const centerY = 96;

                  // Calculate arc path
                  const startAngle = (segment.startAngle - 90) * (Math.PI / 180);
                  const endAngle = (segment.endAngle - 90) * (Math.PI / 180);

                  const x1 = centerX + radius * Math.cos(startAngle);
                  const y1 = centerY + radius * Math.sin(startAngle);
                  const x2 = centerX + radius * Math.cos(endAngle);
                  const y2 = centerY + radius * Math.sin(endAngle);

                  const largeArc = segment.endAngle - segment.startAngle > 180 ? 1 : 0;

                  const pathData = [
                    `M ${centerX} ${centerY}`,
                    `L ${x1} ${y1}`,
                    `A ${radius} ${radius} 0 ${largeArc} 1 ${x2} ${y2}`,
                    'Z',
                  ].join(' ');

                  return (
                    <svg
                      key={index}
                      className="absolute inset-0 w-full h-full"
                      viewBox="0 0 192 192"
                    >
                      <path d={pathData} fill={segment.color} opacity="0.8" />
                    </svg>
                  );
                })}
                {/* Center hole for donut effect */}
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="w-24 h-24 bg-gray-900 rounded-full flex items-center justify-center">
                    <div className="text-center">
                      <div className="text-lg font-bold text-gray-100">
                        {modelBreakdown.length}
                      </div>
                      <div className="text-xs text-gray-400">Models</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Legend */}
            <div className="space-y-2">
              {pieSegments.map((segment, index) => (
                <div key={index} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div
                      className="w-3 h-3 rounded-full"
                      style={{ backgroundColor: segment.color }}
                    />
                    <span className="text-sm text-gray-300">{segment.model}</span>
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-medium text-gray-100">
                      {formatCurrency(segment.total_cost)}
                    </div>
                    <div className="text-xs text-gray-500">
                      {segment.request_count} requests ({segment.percentage.toFixed(1)}%)
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Cost Trend */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-blue-400" />
            <span className="text-sm font-medium text-gray-100">Cost Trend</span>
          </div>
          <div className="flex gap-1">
            {(['day', 'week', 'month', 'all'] as const).map((filter) => (
              <button
                key={filter}
                onClick={() => setTimeFilter(filter)}
                className={`px-2 py-1 text-xs rounded transition-colors ${
                  timeFilter === filter
                    ? 'bg-blue-500 text-white'
                    : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                }`}
              >
                {filter.charAt(0).toUpperCase() + filter.slice(1)}
              </button>
            ))}
          </div>
        </div>

        {trendData.length === 0 ? (
          <p className="text-center text-gray-500 py-8">No trend data yet</p>
        ) : (
          <div className="h-48 flex items-end gap-1">
            {trendData.slice(-20).map((point, index) => {
              const maxCost = Math.max(...trendData.map((p) => p.cost));
              const height = maxCost > 0 ? (point.cost / maxCost) * 100 : 0;

              return (
                <div key={index} className="flex-1 flex flex-col items-center group">
                  <div
                    className="w-full bg-blue-500 rounded-t transition-all hover:bg-blue-400"
                    style={{ height: `${height}%`, minHeight: height > 0 ? '4px' : '0' }}
                    title={`${point.date}: ${formatCurrency(point.cost)}`}
                  />
                  {index % 5 === 0 && (
                    <span className="text-xs text-gray-500 mt-1 rotate-45 origin-left">
                      {new Date(point.date).toLocaleDateString()}
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Recent Costs Table */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <div className="flex items-center gap-2 mb-4">
          <BarChart3 className="w-4 h-4 text-blue-400" />
          <span className="text-sm font-medium text-gray-100">Recent Costs</span>
        </div>

        {recentCosts.length === 0 ? (
          <p className="text-center text-gray-500 py-8">No cost entries yet</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-gray-800">
                <tr className="text-left text-gray-400">
                  <th className="pb-2 font-medium">Task</th>
                  <th className="pb-2 font-medium">Model</th>
                  <th className="pb-2 font-medium">Cost</th>
                  <th className="pb-2 font-medium">Duration</th>
                  <th className="pb-2 font-medium">Timestamp</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {recentCosts.slice(0, 10).map((entry, index) => (
                  <tr key={index} className="text-gray-300 hover:bg-gray-800/50">
                    <td className="py-2">
                      {entry.task_id ? (
                        <div>
                          <div className="font-medium">Task #{entry.task_id}</div>
                          {entry.task_description && (
                            <div className="text-xs text-gray-500 truncate max-w-xs">
                              {entry.task_description}
                            </div>
                          )}
                        </div>
                      ) : (
                        <span className="text-gray-500">Session</span>
                      )}
                    </td>
                    <td className="py-2">
                      <span className="px-2 py-0.5 rounded bg-blue-500/20 text-blue-400 text-xs">
                        {entry.model}
                      </span>
                    </td>
                    <td className="py-2 font-mono">{formatCurrency(entry.cost)}</td>
                    <td className="py-2 text-gray-500">
                      {entry.duration ? `${entry.duration.toFixed(0)}s` : '-'}
                    </td>
                    <td className="py-2 text-gray-500 text-xs">{formatDate(entry.timestamp)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
