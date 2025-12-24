# Email Template Variables

Use these placeholders in email templates and automation actions.
Variables are case-scoped and use a flat namespace:

## Case Variables
- `{{full_name}}` - Case contact full name
- `{{email}}` - Case contact email
- `{{phone}}` - Case contact phone (normalized)
- `{{case_number}}` - Internal case number
- `{{status_label}}` - Case status (human-readable)
- `{{state}}` - Case state
- `{{owner_name}}` - Current owner (user or queue)
- `{{org_name}}` - Organization name

## Status Change Variables
Used in status update workflows:
- `{{new_status}}` - The new status label after change
- `{{old_status}}` - The previous status label

## Appointment Variables
Used in appointment reminder and confirmation emails:
- `{{appointment_date}}` - Formatted date (e.g., "Monday, January 15, 2025")
- `{{appointment_time}}` - Formatted time in org timezone (e.g., "2:30 PM EST")
- `{{appointment_location}}` - Location/address or "Virtual Meeting"

## Intended Parent Variables
- `{{partner1_first_name}}` - Primary partner first name
- `{{partner1_last_name}}` - Primary partner last name
- `{{ip_email}}` - Intended parent email
