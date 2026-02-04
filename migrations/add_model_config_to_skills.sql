-- Migration: Add model_config column to skills table
-- Date: 2026-02-04
-- Description: Adds optional model configuration support for skills

ALTER TABLE skills
ADD COLUMN IF NOT EXISTS model_config JSONB;

-- Add comment
COMMENT ON COLUMN skills.model_config IS 'Optional model configuration (provider, model_name, temperature, etc.)';
