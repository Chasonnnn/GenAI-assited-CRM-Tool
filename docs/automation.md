# Automation System Documentation

**Last Updated:** 2025-12-25  
**Version:** 0.15.00

This document describes the automation system for Surrogacy Force, including workflows, campaigns, and email templates.

---

## Table of Contents

1. [Workflow Engine](#workflow-engine)
2. [Trigger Types](#trigger-types)
3. [Conditions](#conditions)
4. [Actions](#actions)
5. [Email Templates](#email-templates)
6. [Campaigns Module](#campaigns-module)
7. [API Reference](#api-reference)

---

## Workflow Engine

The workflow engine automatically executes actions based on events occurring in Surrogacy Force.

### Architecture

```
Trigger Event → Evaluate Conditions → Execute Actions
     ↓                  ↓                    ↓
  case_created    field == value      send_email
  status_changed  stage in [...]      create_task
  note_added      is_priority == true assign_case
```

### Workflow Model

```python
AutomationWorkflow:
    id: UUID
    organization_id: UUID
    name: str
    description: str
    trigger_type: WorkflowTriggerType
    trigger_config: dict       # Trigger-specific config
    conditions: list[dict]     # Field/operator/value rules
    condition_logic: str       # "AND" or "OR"
    actions: list[dict]        # Action definitions
    is_enabled: bool
    is_system_workflow: bool   # True for default workflows
    system_key: str            # Unique key for system workflows
```

---

## Trigger Types

| Trigger | Description | Trigger Config |
|---------|-------------|----------------|
| `case_created` | New case is created | None |
| `status_changed` | Case status changes | `{from_status, to_status}` |
| `case_assigned` | Case ownership changes | `{owner_type}` |
| `case_updated` | Specific fields change | `{fields: [...]}` |
| `task_due` | Task is approaching due date | `{hours_before: 24}` |
| `task_overdue` | Task passes due date | None |
| `scheduled` | Recurring schedule | `{cron: "0 9 * * 1"}` |
| `inactivity` | No activity on case | `{days: 7}` |
| `appointment_scheduled` | Appointment is confirmed | None |
| `appointment_completed` | Appointment marked complete | None |
| `note_added` | Note added to entity | None |
| `document_uploaded` | File uploaded to case | None |
| `match_proposed` | New match is proposed | None |
| `match_accepted` | Match is accepted | None |
| `match_rejected` | Match is rejected | None |

### Where Triggers Fire

Triggers are called from service layer functions:
- `case_service.create_case()` → `case_created`
- `case_service.update_case()` → `status_changed`, `case_updated`, `case_assigned`
- `note_service.create_note()` → `note_added`
- `attachment_service.mark_attachment_scanned()` → `document_uploaded`
- `appointment_service.approve_booking()` → `appointment_scheduled`
- `matches.py:create_match()` → `match_proposed`
- `matches.py:accept_match()` → `match_accepted`
- `matches.py:reject_match()` → `match_rejected`

---

## Conditions

Conditions filter which entities trigger the workflow.

### Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `equals` | Exact match | `status == "approved"` |
| `not_equals` | Not equal | `source != "import"` |
| `contains` | Substring match | `email contains "@gmail"` |
| `not_contains` | Substring not present | |
| `in` | Value in list | `stage_id in [uuid1, uuid2]` |
| `not_in` | Value not in list | |
| `greater_than` | Numeric comparison | `age > 21` |
| `less_than` | Numeric comparison | `bmi < 32` |
| `is_empty` | Field is null/empty | |
| `is_not_empty` | Field has value | |

### Condition Logic

- **AND**: All conditions must match
- **OR**: Any condition must match

```json
{
  "conditions": [
    {"field": "state", "operator": "in", "value": ["CA", "TX", "FL"]},
    {"field": "is_priority", "operator": "equals", "value": true}
  ],
  "condition_logic": "AND"
}
```

---

## Actions

Actions are executed when conditions match.

### Action Types

| Action | Description | Config |
|--------|-------------|--------|
| `send_email` | Send email from template | `{template_id, recipient_type}` |
| `create_task` | Create task on case | `{title, task_type, due_days, owner_type}` |
| `assign_case` | Assign case ownership | `{owner_type, owner_id}` |
| `send_notification` | In-app notification | `{title, message, recipients}` |
| `update_field` | Update case field | `{field, value}` |
| `add_note` | Add note to case | `{content, is_internal}` |

### Action Delay

Actions can have optional delay:
```json
{
  "action_type": "send_email",
  "template_id": "uuid",
  "delay_minutes": 60
}
```

### Entity-Type Restrictions

Some actions only work with Case or Task entities:

| Action | Supported Entity Types |
|--------|------------------------|
| `send_email` | Case, Task |
| `create_task` | Case, Task |
| `assign_case` | Case, Task |
| `update_field` | Case, Task |
| `add_note` | Case, Task |
| `send_notification` | All entities |

If a workflow triggers on non-Case entities (match, appointment, note, document), only `send_notification` will execute; other actions return a validation error.

---

## Email Templates

### Template Model

```python
EmailTemplate:
    id: UUID
    organization_id: UUID
    name: str
    subject: str
    body: str                  # HTML with {{variables}}
    system_key: str            # For system templates
    is_active: bool
    requires_review: bool      # True for AI-generated
```

### Default Templates

10 templates are auto-seeded on first user login:

1. **Welcome New Lead** - Initial lead greeting
2. **Application Next Steps** - Post-application guidance
3. **Document Request** - Request missing documents
4. **Appointment Reminder (24h)** - Day-before reminder
5. **Appointment Confirmed** - Booking confirmation
6. **Status Update** - Notify on status change
7. **Match Proposal Introduction** - IP-Surrogate intro
8. **Match Accepted Congratulations** - Match success
9. **Inactivity Follow-up** - Re-engagement
10. **Contract Ready for Review** - Legal docs ready

### Template Variables

See [email-template-variables.md](./email-template-variables.md) for full list:
- `{{full_name}}`, `{{email}}`, `{{phone}}`
- `{{surrogate_number}}`, `{{status_label}}`, `{{owner_name}}`
- `{{appointment_date}}`, `{{appointment_time}}`, `{{appointment_location}}`
- `{{new_status}}`, `{{old_status}}`

---

## Campaigns Module

Campaigns enable bulk email sends to filtered recipient lists.

### Campaign Model

```python
Campaign:
    id: UUID
    organization_id: UUID
    name: str
    email_template_id: UUID
    recipient_type: str        # "case" or "intended_parent"
    filter_criteria: dict      # Recipient filters
    status: CampaignStatus     # draft, scheduled, running, completed
    scheduled_at: datetime
```

### Recipient Filtering

```json
{
  "stage_ids": ["uuid1", "uuid2"],
  "stage_slugs": ["qualified", "applied"],
  "states": ["CA", "TX"],
  "created_after": "2024-01-01",
  "created_before": "2024-12-31",
  "source": "meta",
  "is_priority": true
}
```

### Campaign Runs

Each send creates a `CampaignRun` with:
- Total recipients
- Sent count, failed count, skipped count
- Per-recipient status tracking

### Email Suppression

Org-scoped suppression list for:
- Bounced emails
- Unsubscribes
- Manual suppressions

---

## API Reference

### Workflow Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/workflows` | GET | List org workflows |
| `/workflows` | POST | Create workflow |
| `/workflows/options` | GET | Get trigger/action options |
| `/workflows/stats` | GET | Dashboard stats |
| `/workflows/{id}` | GET | Get workflow |
| `/workflows/{id}` | PATCH | Update workflow |
| `/workflows/{id}` | DELETE | Delete workflow |
| `/workflows/{id}/toggle` | POST | Enable/disable |
| `/workflows/{id}/test` | POST | Dry run test |

### Campaign Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/campaigns` | GET | List campaigns |
| `/campaigns` | POST | Create campaign |
| `/campaigns/{id}` | GET | Get campaign |
| `/campaigns/{id}` | PATCH | Update (draft only) |
| `/campaigns/{id}/send` | POST | Enqueue for sending |
| `/campaigns/{id}/cancel` | POST | Cancel scheduled |
| `/campaigns/preview` | POST | Preview recipients |
| `/campaigns/suppressions` | GET | List suppressions |

### Template Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/email-templates` | GET | List templates |
| `/email-templates` | POST | Create template |
| `/email-templates/{id}` | PATCH | Update template |
| `/email-templates/{id}/preview` | POST | Render preview |

---

## Security Considerations

### Multi-Tenancy

- All queries scoped by `organization_id`
- Stage slug filtering joins through Pipeline for org validation
- Template updates verify org ownership

### Idempotency

- Campaign sends use idempotency keys: `campaign:{id}:run:{run_id}`
- Workflow executions logged to prevent duplicate actions

### Rate Limiting

- Bulk operations protected by slowapi rate limiter
- Email sends use job queue for throttling

---

*Last updated: 2025-12-25*
