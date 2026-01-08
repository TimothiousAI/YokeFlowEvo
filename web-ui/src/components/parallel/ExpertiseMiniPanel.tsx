'use client';

import React, { useState } from 'react';
import {
  Brain,
  ChevronDown,
  ChevronRight,
  TrendingUp,
  Clock,
  Sparkles,
  BookOpen,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type { LearningEvent, DomainSummary } from './hooks/useParallelState';

interface ExpertiseMiniPanelProps {
  recentLearnings: LearningEvent[];
  domainSummaries: DomainSummary[];
  onViewDetails?: () => void;
  className?: string;
}

function formatTimeAgo(date: Date): string {
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ago`;
}

function getDomainColor(domain: string): string {
  const colors: Record<string, string> = {
    backend: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    frontend: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
    database: 'bg-green-500/20 text-green-400 border-green-500/30',
    testing: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    orchestration: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
    mcp: 'bg-pink-500/20 text-pink-400 border-pink-500/30',
  };
  return colors[domain.toLowerCase()] || 'bg-gray-500/20 text-gray-400 border-gray-500/30';
}

export function ExpertiseMiniPanel({
  recentLearnings,
  domainSummaries,
  onViewDetails,
  className,
}: ExpertiseMiniPanelProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const totalPatterns = domainSummaries.reduce((sum, d) => sum + d.patternCount, 0);
  const totalTechniques = domainSummaries.reduce((sum, d) => sum + d.techniqueCount, 0);

  return (
    <div
      className={cn(
        'rounded-lg border border-gray-700 bg-gray-800/50 backdrop-blur-sm overflow-hidden',
        className
      )}
    >
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full p-3 flex items-center justify-between hover:bg-gray-700/30 transition-colors"
      >
        <div className="flex items-center gap-3">
          {isExpanded ? (
            <ChevronDown className="w-4 h-4 text-gray-400" />
          ) : (
            <ChevronRight className="w-4 h-4 text-gray-400" />
          )}

          <Brain className="w-5 h-5 text-purple-400" />
          <span className="font-semibold text-gray-100">
            Expertise Learning
          </span>
        </div>

        {/* Quick Stats */}
        <div className="flex items-center gap-3 text-xs text-gray-400">
          {domainSummaries.length > 0 && (
            <>
              <span className="flex items-center gap-1">
                <BookOpen className="w-3 h-3" />
                {domainSummaries.length} domains
              </span>
              <span className="hidden sm:flex items-center gap-1">
                <TrendingUp className="w-3 h-3" />
                {totalPatterns} patterns
              </span>
            </>
          )}
          {recentLearnings.length > 0 && (
            <span className="flex items-center gap-1 text-green-400">
              <Sparkles className="w-3 h-3" />
              {recentLearnings.length} new
            </span>
          )}
        </div>
      </button>

      {/* Collapsed Summary */}
      {!isExpanded && domainSummaries.length > 0 && (
        <div className="px-3 pb-3 flex flex-wrap gap-2">
          {domainSummaries.slice(0, 6).map(domain => (
            <span
              key={domain.domain}
              className={cn(
                'px-2 py-0.5 rounded text-xs font-medium border',
                getDomainColor(domain.domain)
              )}
            >
              {domain.domain}: {domain.patternCount}
            </span>
          ))}
          {domainSummaries.length > 6 && (
            <span className="px-2 py-0.5 rounded text-xs text-gray-500">
              +{domainSummaries.length - 6} more
            </span>
          )}
        </div>
      )}

      {/* Expanded View */}
      {isExpanded && (
        <div className="p-3 pt-0 border-t border-gray-700/50 space-y-4">
          {/* Domain Summary Grid */}
          {domainSummaries.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs text-gray-500 uppercase tracking-wide">
                Domain Knowledge
              </p>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {domainSummaries.map(domain => (
                  <div
                    key={domain.domain}
                    className={cn(
                      'p-2 rounded-lg border',
                      getDomainColor(domain.domain)
                    )}
                  >
                    <div className="font-medium text-sm capitalize">
                      {domain.domain}
                    </div>
                    <div className="text-xs opacity-80 mt-1">
                      {domain.patternCount} patterns • {domain.techniqueCount} techniques
                    </div>
                    <div className="text-xs opacity-60 mt-0.5">
                      Updated: {formatTimeAgo(domain.lastUpdated)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Recent Learnings */}
          {recentLearnings.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs text-gray-500 uppercase tracking-wide">
                Recent Learnings
              </p>
              <div className="space-y-1.5 max-h-40 overflow-y-auto">
                {recentLearnings.slice(0, 10).map((learning, i) => (
                  <div
                    key={`${learning.taskId}-${i}`}
                    className="flex items-center gap-2 p-2 rounded-lg bg-gray-900/50 border border-gray-700/50"
                  >
                    <Sparkles className="w-3 h-3 text-green-400 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <span className="text-sm text-gray-200">
                        Task #{learning.taskId}
                      </span>
                      <span className="text-gray-500 mx-1">→</span>
                      <span className={cn(
                        'text-sm font-medium',
                        getDomainColor(learning.domain).split(' ')[1] // Extract text color
                      )}>
                        {learning.domain}
                      </span>
                      <span className="text-xs text-gray-500 ml-2">
                        +{learning.patternsLearned} patterns
                      </span>
                    </div>
                    <div className="text-xs text-gray-500 flex-shrink-0">
                      <Clock className="w-3 h-3 inline mr-1" />
                      {formatTimeAgo(learning.timestamp)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Empty State */}
          {domainSummaries.length === 0 && recentLearnings.length === 0 && (
            <div className="text-center py-4">
              <Brain className="w-8 h-8 text-gray-600 mx-auto mb-2" />
              <p className="text-sm text-gray-500">
                No expertise learned yet
              </p>
              <p className="text-xs text-gray-600 mt-1">
                Expertise will accumulate as tasks complete
              </p>
            </div>
          )}

          {/* View Details Button */}
          {onViewDetails && domainSummaries.length > 0 && (
            <button
              onClick={onViewDetails}
              className="w-full py-2 text-sm text-blue-400 hover:text-blue-300 hover:bg-blue-500/10 rounded-lg transition-colors"
            >
              View Full Expertise Details →
            </button>
          )}
        </div>
      )}
    </div>
  );
}
