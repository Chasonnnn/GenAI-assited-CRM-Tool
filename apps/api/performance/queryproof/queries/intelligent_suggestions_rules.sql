SELECT r.rule_kind, r.stage_slug, r.business_days, r.sort_order FROM public.org_intelligent_suggestion_rules AS r WHERE r.organization_id = $1 AND r.enabled = TRUE ORDER BY r.sort_order;
