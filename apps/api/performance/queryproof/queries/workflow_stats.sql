SELECT e.status, count(*), avg(e.duration_ms) FROM public.workflow_executions AS e WHERE e.organization_id = $1 AND e.executed_at >= $2 GROUP BY e.status;
