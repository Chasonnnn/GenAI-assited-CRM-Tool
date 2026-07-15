SELECT s.id, s.stage_id, s.status_label, s.owner_type, s.owner_id, s.created_at, s.updated_at FROM public.surrogates AS s WHERE s.organization_id = $1 AND s.id = $2 AND s.is_archived = FALSE;
