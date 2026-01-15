# Email Template Variables

Use these placeholders in email templates and automation actions.
Variables are surrogate-scoped and use a flat namespace:

## Surrogate Variables
- `{{full_name}}` - Surrogate full name
- `{{email}}` - Surrogate email
- `{{phone}}` - Surrogate phone (normalized)
- `{{surrogate_number}}` - Internal surrogate number (S10001+)
- `{{status_label}}` - Surrogate status (human-readable)
- `{{state}}` - Surrogate state
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
- `{{intended_parent_number}}` - Internal intended parent number (I10001+)
