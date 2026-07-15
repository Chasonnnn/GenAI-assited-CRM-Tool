UPDATE public.tasks SET is_completed = TRUE, completed_at = $3, updated_at = $3 WHERE organization_id = $1 AND id = $2 RETURNING id;
