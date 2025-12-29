-- Migration: Add metadata column to prompt_proposals table
--
-- Background: The prompt_improvement_analyzer.py code stores diff details
-- and other supplementary data in a metadata JSONB column, but this column
-- was missing from the schema.
--
-- This migration adds the missing column for existing installations.

-- Add the metadata column
ALTER TABLE prompt_proposals
  ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';

COMMENT ON COLUMN prompt_proposals.metadata IS 'Supplementary data including diff details, statistics, and other analysis metadata';
