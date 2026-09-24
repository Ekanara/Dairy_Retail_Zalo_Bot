-- ============================================================
-- Magic Sale AI — PostgreSQL Initialisation Script
-- Runs once on first container start via docker-entrypoint-initdb.d
-- ============================================================

-- Enable required PostgreSQL extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";    -- UUID primary keys
CREATE EXTENSION IF NOT EXISTS "pgcrypto";     -- gen_random_uuid(), crypt()
CREATE EXTENSION IF NOT EXISTS "vector";       -- pgvector for RAG semantic search

-- Grant full privileges to the application user
GRANT ALL PRIVILEGES ON DATABASE magic_sale TO postgres;
