---
status: accepted
---

# Medical and insurance details are dated records

Surrogate and donor medical and insurance details live in `medical_records`, one row per record, owned by exactly one surrogate or donor. The sections are `insurance`, `pcp`, `lab_clinic`, `clinic`, `monitoring_clinic`, `ob` and `delivery_hospital`. Every section can hold any number of records. A record has an `effective_date`; imported records have none.

Placement is computed on read against the organization's local date. The current record is the latest record whose effective date is empty or not after today, unless that record is archived. Records dated after today are scheduled. A past record ends the day before the next record starts, or on its archive date if that is earlier.

Editing a field corrects the record in place. Each correction stores the field, old value, new value, source and user, encrypted like the record. Member ID, policy number and subscriber date of birth store no values; their corrections show only that the field changed. Writes take an `expected_revision` and return 409 when it is stale. Changing the name, provider or policy identity of the current record asks whether it is a new record; a new record copies details from any existing record.

Archiving ends the current record today and keeps its history. Restoring an archived section creates a new record dated today with the archived record's details. Create and restore accept an idempotency key. Form answers mapped to the former flat field names correct the current record, or start a record dated on the submission date when the section has none.

The migration copies each non-empty flat section into one imported record. The former flat columns on `surrogates` and `donors` stay in the database unused, and payloads that send them are rejected. A follow-up migration drops the columns once this release is verified in production.

## Considered Options

- Keep flat columns with an audit log: rejected. It records edits but cannot hold a scheduled change or show which provider was current on a past date.
- A history drawer beside the flat fields: rejected. Two places for the same data, and the drawer still needs dated rows.
- Mark records as verified each year: rejected. Staff create a new dated record when details change.
