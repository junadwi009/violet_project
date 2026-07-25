CREATE TABLE IF NOT EXISTS agent_runs (
  id TEXT PRIMARY KEY,
  session_id TEXT,
  agent_id TEXT,
  status TEXT NOT NULL,
  messages_json TEXT NOT NULL,
  pending_json TEXT,
  iterations INTEGER DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_agent_runs_session ON agent_runs(session_id);
