# Email Template Variables

Use these placeholders in email templates and automation actions.
Variables are case-scoped and use a flat namespace:

- `{{full_name}}` - Case contact full name
- `{{email}}` - Case contact email
- `{{phone}}` - Case contact phone (normalized)
- `{{case_number}}` - Internal case number
- `{{status}}` - Case status (human-readable)
- `{{state}}` - Case state
- `{{owner_name}}` - Current owner (user or queue)
- `{{org_name}}` - Organization name
