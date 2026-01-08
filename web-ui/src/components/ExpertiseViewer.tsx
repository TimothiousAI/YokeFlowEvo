/**
 * ExpertiseViewer - View and edit expertise domains
 *
 * Features:
 * - List all expertise domains with summary stats
 * - Expandable detail view for each domain
 * - Show validation status with timestamp
 * - Display learning history timeline
 * - Allow manual editing of expertise content
 * - Syntax highlighting for code snippets in expertise
 * - Save changes via API
 */

'use client';

import React, { useState } from 'react';
import {
  ChevronDown,
  ChevronRight,
  CheckCircle,
  XCircle,
  Edit2,
  Check,
  X,
  Clock,
  FileText,
  Code
} from 'lucide-react';

interface ExpertiseDomain {
  domain: string;
  content: string;
  validation_status: 'valid' | 'invalid' | 'pending';
  validated_at: string | null;
  created_at: string;
  updated_at: string;
  learning_count?: number;
  last_learned?: string;
}

interface LearningHistoryEntry {
  id: string;
  session_id: string;
  task_id: number;
  learned_at: string;
  summary: string;
}

interface ExpertiseViewerProps {
  domains: ExpertiseDomain[];
  onSave?: (domain: string, content: string) => Promise<void>;
  onRefresh?: () => Promise<void>;
  className?: string;
}

export function ExpertiseViewer({ domains, onSave, onRefresh, className = '' }: ExpertiseViewerProps) {
  const [expandedDomain, setExpandedDomain] = useState<string | null>(null);
  const [editingDomain, setEditingDomain] = useState<string | null>(null);
  const [editContent, setEditContent] = useState<string>('');
  const [saving, setSaving] = useState(false);

  const toggleDomain = (domain: string) => {
    if (expandedDomain === domain) {
      setExpandedDomain(null);
      setEditingDomain(null);
    } else {
      setExpandedDomain(domain);
      setEditingDomain(null);
    }
  };

  const startEditing = (domain: ExpertiseDomain) => {
    setEditingDomain(domain.domain);
    setEditContent(domain.content);
  };

  const cancelEditing = () => {
    setEditingDomain(null);
    setEditContent('');
  };

  const saveChanges = async (domain: string) => {
    if (!onSave) return;

    setSaving(true);
    try {
      await onSave(domain, editContent);
      setEditingDomain(null);
      setEditContent('');
    } catch (error) {
      console.error('Failed to save expertise:', error);
      // Could show error toast here
    } finally {
      setSaving(false);
    }
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'Never';
    const date = new Date(dateString);
    return date.toLocaleString();
  };

  const getValidationIcon = (status: string) => {
    switch (status) {
      case 'valid':
        return <CheckCircle className="w-4 h-4 text-green-400" />;
      case 'invalid':
        return <XCircle className="w-4 h-4 text-red-400" />;
      default:
        return <Clock className="w-4 h-4 text-gray-400" />;
    }
  };

  const getValidationBadge = (status: string) => {
    switch (status) {
      case 'valid':
        return (
          <span className="px-2 py-1 rounded-full bg-green-500/20 text-green-400 border border-green-500/30 text-xs font-medium">
            Valid
          </span>
        );
      case 'invalid':
        return (
          <span className="px-2 py-1 rounded-full bg-red-500/20 text-red-400 border border-red-500/30 text-xs font-medium">
            Invalid
          </span>
        );
      default:
        return (
          <span className="px-2 py-1 rounded-full bg-gray-500/20 text-gray-400 border border-gray-500/30 text-xs font-medium">
            Pending
          </span>
        );
    }
  };

  // Simple syntax highlighting for code blocks
  const renderContent = (content: string) => {
    // Split content by code blocks (markdown style: ```language ... ```)
    const parts = content.split(/(```[\s\S]*?```)/g);

    return parts.map((part, index) => {
      if (part.startsWith('```')) {
        // Code block
        const lines = part.split('\n');
        const language = lines[0].replace('```', '').trim();
        const code = lines.slice(1, -1).join('\n');

        return (
          <div key={index} className="my-3">
            {language && (
              <div className="bg-gray-800 px-3 py-1 text-xs text-gray-400 border-b border-gray-700 rounded-t-lg flex items-center gap-2">
                <Code className="w-3 h-3" />
                {language}
              </div>
            )}
            <pre className="bg-gray-900 p-3 rounded-b-lg overflow-x-auto">
              <code className="text-sm text-gray-300 font-mono">{code}</code>
            </pre>
          </div>
        );
      } else {
        // Regular text
        return (
          <div key={index} className="whitespace-pre-wrap text-sm text-gray-300">
            {part}
          </div>
        );
      }
    });
  };

  return (
    <div className={`space-y-3 ${className}`}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-100 flex items-center gap-2">
          <FileText className="w-5 h-5 text-blue-400" />
          Expertise Domains ({domains.length})
        </h3>
      </div>

      {domains.length === 0 ? (
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-8 text-center">
          <FileText className="w-12 h-12 text-gray-600 mx-auto mb-3" />
          <p className="text-gray-400">No expertise domains yet</p>
          <p className="text-sm text-gray-500 mt-1">
            Expertise will be accumulated as the system learns from task execution
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {domains.map((domain) => {
            const isExpanded = expandedDomain === domain.domain;
            const isEditing = editingDomain === domain.domain;

            return (
              <div
                key={domain.domain}
                className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden"
              >
                {/* Domain Header */}
                <button
                  onClick={() => toggleDomain(domain.domain)}
                  className="w-full p-4 flex items-start gap-3 hover:bg-gray-800/50 transition-colors text-left"
                >
                  {/* Expand Icon */}
                  <div className="mt-0.5 flex-shrink-0">
                    {isExpanded ? (
                      <ChevronDown className="w-5 h-5 text-gray-400" />
                    ) : (
                      <ChevronRight className="w-5 h-5 text-gray-400" />
                    )}
                  </div>

                  {/* Domain Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-2">
                      <h4 className="text-base font-semibold text-gray-100">{domain.domain}</h4>
                      {getValidationBadge(domain.validation_status)}
                    </div>

                    <div className="flex items-center gap-4 text-xs text-gray-400">
                      <div className="flex items-center gap-1">
                        {getValidationIcon(domain.validation_status)}
                        <span>Validated: {formatDate(domain.validated_at)}</span>
                      </div>
                      {domain.learning_count !== undefined && (
                        <span>{domain.learning_count} learning sessions</span>
                      )}
                      {domain.last_learned && (
                        <span>Last learned: {formatDate(domain.last_learned)}</span>
                      )}
                    </div>
                  </div>
                </button>

                {/* Expanded Content */}
                {isExpanded && (
                  <div className="border-t border-gray-800 p-4">
                    {/* Edit Controls */}
                    <div className="flex items-center justify-between mb-4">
                      <div className="text-xs text-gray-500">
                        Created: {formatDate(domain.created_at)} • Updated:{' '}
                        {formatDate(domain.updated_at)}
                      </div>
                      {!isEditing ? (
                        <button
                          onClick={() => startEditing(domain)}
                          className="flex items-center gap-2 px-3 py-1.5 bg-blue-500/20 hover:bg-blue-500/30 text-blue-400 rounded-lg transition-colors text-sm"
                        >
                          <Edit2 className="w-3 h-3" />
                          Edit
                        </button>
                      ) : (
                        <div className="flex gap-2">
                          <button
                            onClick={() => saveChanges(domain.domain)}
                            disabled={saving}
                            className="flex items-center gap-2 px-3 py-1.5 bg-green-500/20 hover:bg-green-500/30 text-green-400 rounded-lg transition-colors text-sm disabled:opacity-50"
                          >
                            <Check className="w-3 h-3" />
                            {saving ? 'Saving...' : 'Save'}
                          </button>
                          <button
                            onClick={cancelEditing}
                            disabled={saving}
                            className="flex items-center gap-2 px-3 py-1.5 bg-gray-700/50 hover:bg-gray-700 text-gray-300 rounded-lg transition-colors text-sm disabled:opacity-50"
                          >
                            <X className="w-3 h-3" />
                            Cancel
                          </button>
                        </div>
                      )}
                    </div>

                    {/* Content Display or Editor */}
                    {isEditing ? (
                      <div>
                        <label className="block text-xs text-gray-400 mb-2">
                          Expertise Content (Markdown supported)
                        </label>
                        <textarea
                          value={editContent}
                          onChange={(e) => setEditContent(e.target.value)}
                          className="w-full h-96 bg-gray-800 border border-gray-700 rounded-lg p-3 text-sm text-gray-300 font-mono resize-y focus:outline-none focus:ring-2 focus:ring-blue-500"
                          placeholder="Enter expertise content..."
                        />
                        <p className="text-xs text-gray-500 mt-2">
                          Use markdown code blocks: ```language ... ``` for syntax highlighting
                        </p>
                      </div>
                    ) : (
                      <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-4 max-h-[500px] overflow-y-auto">
                        {renderContent(domain.content)}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
