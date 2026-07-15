SELECT ps.id, ps.stage_key, ps.stage_type, ps.order FROM public.pipeline_stages AS ps WHERE ps.pipeline_id = $1 AND ps.is_active = TRUE ORDER BY ps.order;
