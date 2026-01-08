'use client';

import React from 'react';
import { ChevronDown, ArrowDown } from 'lucide-react';
import { cn } from '@/lib/utils';

interface BatchConnectorProps {
  /** Whether the source batch is complete */
  isComplete?: boolean;
  /** Whether the connection is active (data flowing) */
  isActive?: boolean;
  /** Whether there's a merge point in this connection */
  hasMerge?: boolean;
  /** Custom height for the connector */
  height?: number;
  className?: string;
}

export function BatchConnector({
  isComplete = false,
  isActive = false,
  hasMerge = false,
  height = 40,
  className,
}: BatchConnectorProps) {
  return (
    <div
      className={cn('relative flex flex-col items-center', className)}
      style={{ height: `${height}px` }}
    >
      {/* Connection Line */}
      <div
        className={cn(
          'w-0.5 flex-1 transition-colors duration-500',
          isComplete ? 'bg-green-500' :
          isActive ? 'bg-blue-500' : 'bg-gray-600',
          isActive && !isComplete && 'animate-pulse'
        )}
      />

      {/* Arrow or Flow Indicator */}
      <div
        className={cn(
          'absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2',
          'transition-colors duration-500'
        )}
      >
        {isActive && !isComplete ? (
          <div className="relative">
            {/* Animated flow dots */}
            <div className="flex flex-col items-center gap-1">
              <div
                className="w-1.5 h-1.5 rounded-full bg-blue-400"
                style={{
                  animation: 'flowDown 1.5s infinite',
                  animationDelay: '0s',
                }}
              />
              <div
                className="w-1.5 h-1.5 rounded-full bg-blue-400"
                style={{
                  animation: 'flowDown 1.5s infinite',
                  animationDelay: '0.5s',
                }}
              />
              <div
                className="w-1.5 h-1.5 rounded-full bg-blue-400"
                style={{
                  animation: 'flowDown 1.5s infinite',
                  animationDelay: '1s',
                }}
              />
            </div>
          </div>
        ) : (
          <ChevronDown
            className={cn(
              'w-4 h-4',
              isComplete ? 'text-green-400' : 'text-gray-500'
            )}
          />
        )}
      </div>

      {/* CSS for flow animation */}
      <style jsx>{`
        @keyframes flowDown {
          0% {
            opacity: 0;
            transform: translateY(-8px);
          }
          50% {
            opacity: 1;
          }
          100% {
            opacity: 0;
            transform: translateY(8px);
          }
        }
      `}</style>
    </div>
  );
}

/**
 * Horizontal connector for parallel sessions within a batch
 */
interface ParallelConnectorProps {
  count: number;
  className?: string;
}

export function ParallelConnector({ count, className }: ParallelConnectorProps) {
  if (count <= 1) return null;

  return (
    <div className={cn('relative flex items-center justify-center py-2', className)}>
      {/* Horizontal line connecting all sessions */}
      <div className="absolute top-1/2 left-4 right-4 h-0.5 bg-purple-500/30" />

      {/* Fork points */}
      <div className="flex justify-around w-full relative">
        {Array.from({ length: count }).map((_, i) => (
          <div key={i} className="flex flex-col items-center">
            <div className="w-0.5 h-3 bg-purple-500/50" />
            <div className="w-2 h-2 rounded-full bg-purple-500 border-2 border-gray-900" />
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Merge connector that shows multiple lines converging
 */
interface MergeConnectorProps {
  inputCount: number;
  isComplete?: boolean;
  className?: string;
}

export function MergeConnector({ inputCount, isComplete = false, className }: MergeConnectorProps) {
  return (
    <div className={cn('relative h-12 flex items-center justify-center', className)}>
      <svg className="w-full h-full" viewBox="0 0 200 50" preserveAspectRatio="xMidYMid meet">
        {/* Input lines */}
        {Array.from({ length: inputCount }).map((_, i) => {
          const startX = 20 + (i * (160 / (inputCount - 1 || 1)));
          return (
            <path
              key={i}
              d={`M ${startX} 0 Q ${startX} 25 100 45`}
              fill="none"
              stroke={isComplete ? '#22c55e' : '#6b7280'}
              strokeWidth="2"
              className={cn(!isComplete && 'animate-pulse')}
            />
          );
        })}

        {/* Center merge point */}
        <circle
          cx="100"
          cy="45"
          r="4"
          fill={isComplete ? '#22c55e' : '#eab308'}
          className={cn(!isComplete && 'animate-pulse')}
        />
      </svg>
    </div>
  );
}

/**
 * Simple vertical arrow connector
 */
export function ArrowConnector({ isComplete = false }: { isComplete?: boolean }) {
  return (
    <div className="flex flex-col items-center py-2">
      <div
        className={cn(
          'w-0.5 h-4',
          isComplete ? 'bg-green-500' : 'bg-gray-600'
        )}
      />
      <ArrowDown
        className={cn(
          'w-4 h-4 -mt-1',
          isComplete ? 'text-green-400' : 'text-gray-500'
        )}
      />
    </div>
  );
}
