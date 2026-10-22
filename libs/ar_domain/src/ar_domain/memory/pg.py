"""pgvector recall statement. Spec: docs/03-specs/11-memory.md §3."""

RECALL_SQL = """
SELECT id,
       content,
       1 - (embedding <=> CAST(:query AS vector)) AS cosine
FROM memory_facts
WHERE status = 'active'
  AND tenant_id = CAST(:tenant AS uuid)
  AND (
        (scope = 'user' AND user_id = CAST(:user_id AS uuid))
     OR (scope = 'agent_user' AND agent_id = CAST(:agent_id AS uuid)
         AND user_id = CAST(:user_id AS uuid))
     OR (scope = 'agent' AND agent_id = CAST(:agent_id AS uuid))
     OR (scope = 'team' AND team_id = ANY(CAST(:team_ids AS uuid[])))
  )
ORDER BY embedding <=> CAST(:query AS vector)
LIMIT 30
"""
