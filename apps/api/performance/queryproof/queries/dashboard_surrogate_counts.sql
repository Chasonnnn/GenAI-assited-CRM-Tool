SELECT s.stage_id, count(*) FROM public.surrogates AS s WHERE s.organization_id = $1 AND s.is_archived = FALSE GROUP BY s.stage_id;
