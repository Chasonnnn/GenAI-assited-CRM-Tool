# Database Optimization Analysis

This document records database optimization opportunities identified during a comprehensive review, including deferred items that require further investigation before implementation.

---

## Completed Optimizations

*To be updated as changes are implemented*

---

## Deferred Optimizations

### 1. Row Level Security (RLS) Implementation

**Status**: Deferred - Major blockers identified

**Original Proposal**: Add RLS policies to all multi-tenant tables using session variables (`SET app.current_org_id`) to enforce organization isolation at the database level.

**Why It Was Deferred**:

1. **Membership Bootstrapping Problem**
   - `get_current_session()` queries the `memberships` table before organization context can be established
   - Enabling org-based RLS on `memberships` would break authentication flow
   - The auth flow needs to query memberships to determine which org the user belongs to, creating a circular dependency

2. **Connection Pool Leakage Risk**
   - Using session GUCs (`SET app.current_org_id = ...`) with SQLAlchemy's connection pooling is dangerous
   - If GUCs aren't properly reset per-transaction, one tenant could inherit another tenant's context from a pooled connection
   - This would be a critical security vulnerability worse than having no RLS at all

3. **Bypass Design Weakness**
   - A simple `app.bypass_rls` flag is not robust without:
     - DB role gating (only specific roles should be able to set bypass)
     - Reliable reset mechanisms
     - Audit logging of bypass usage

**Future Approach**:
- Investigate using Postgres roles per tenant instead of session variables
- Consider RLS only on leaf tables (not `memberships`, `users`, `auth_identities`)
- Add connection cleanup hooks in SQLAlchemy event listeners to reset GUCs
- Research Supabase's approach to RLS with connection pooling (PgBouncer)

**References**:
- `apps/api/app/core/deps.py` - Current auth flow
- `apps/api/app/db/session.py` - Connection pool configuration

---

### 2. Intended Parents Full-Text Search

**Status**: Deferred - Semantic behavior change requires design decision

**Original Proposal**: Replace ILIKE substring search with PostgreSQL full-text search using existing `search_vector` column.

**Current Implementation** (`apps/api/app/services/ip_service.py:132-148`):
```python
if q:
    search_term = f"%{q}%"
    filters = [
        IntendedParent.full_name.ilike(search_term),
        IntendedParent.intended_parent_number.ilike(search_term),
    ]
    # ... hash lookups for email/phone
    query = query.filter(or_(*filters))
```

**Why It Was Deferred**:

1. **Semantic Difference**
   - Current: `ILIKE '%cha%'` matches "Chason", "Michael", "Richard" (substring match)
   - FTS: `plainto_tsquery('cha')` would NOT match these (word boundary match)
   - Users may rely on substring matching behavior

2. **Prefix Search Limitation**
   - Even with prefix search (`to_tsquery('simple', 'cha:*')`), FTS only matches word prefixes
   - "cha" would match "Chason" but not "Michael" or "Richard"

3. **Alternative Approaches Need Evaluation**:

   **Option A: pg_trgm Extension**
   ```sql
   -- Enable trigram extension
   CREATE EXTENSION IF NOT EXISTS pg_trgm;

   -- Create GIN trigram index
   CREATE INDEX idx_intended_parents_name_trgm
   ON intended_parents USING gin (full_name gin_trgm_ops);

   -- Query with trigram similarity
   SELECT * FROM intended_parents
   WHERE full_name % 'cha' OR full_name ILIKE '%cha%';
   ```
   - Pros: True substring matching, fuzzy matching capability
   - Cons: Additional extension, index size overhead

   **Option B: Hybrid Approach**
   ```python
   if len(q) >= 3:
       # Use FTS for longer queries (word matches)
       tsquery = func.plainto_tsquery("simple", q)
       query = query.filter(IntendedParent.search_vector.op("@@")(tsquery))
   else:
       # Fall back to ILIKE for short queries
       query = query.filter(IntendedParent.full_name.ilike(f"%{q}%"))
   ```
   - Pros: Preserves short-query substring behavior
   - Cons: Inconsistent behavior based on query length

   **Option C: Accept Behavior Change**
   - Document that search now matches word prefixes only
   - May actually be desired behavior for name searches

**Requirements Before Implementation**:
1. Product decision on desired search behavior
2. User research on current search patterns
3. Comprehensive test suite for search results
4. Migration plan if behavior changes

**References**:
- `apps/api/app/db/models.py:2082-2086` - IntendedParent search_vector definition
- `apps/api/app/services/search_service.py:678+` - Global search implementation (uses FTS)

---

### 3. Redundant Index Proposals (Not Needed)

The following indexes were initially proposed but determined to be unnecessary:

#### campaign_runs (campaign_id, started_at DESC)

**Why Not Needed**:
- Existing index: `Index("idx_campaign_runs_campaign", "campaign_id", "started_at")` in `apps/api/app/db/models.py`
- PostgreSQL can scan a B-tree index backward for `ORDER BY started_at DESC`
- Adding a separate DESC index is redundant write amplification

#### campaign_recipients (run_id, entity_type, entity_id)

**Why Not Needed**:
- Existing constraint: `UniqueConstraint("run_id", "entity_type", "entity_id", name="uq_campaign_recipient")`
- Unique constraints automatically create indexes on the constrained columns
- Additional indexes: `idx_campaign_recipients_run` and `idx_campaign_recipients_entity`

#### tasks (organization_id, is_completed, due_date)

**Why Likely Redundant**:
- Existing index: `idx_tasks_org_status` on `(organization_id, is_completed)`
- Existing partial index: `idx_tasks_due` on `(organization_id, due_date)` WHERE `is_completed = FALSE`
- The composite index might help "mixed completed+incomplete" ordering, but likely unnecessary write amplification
- Should only add after EXPLAIN ANALYZE shows clear benefit

---

## Validated Optimizations (Ready to Implement)

### 1. Campaign Service N+1 Fix

**File**: `apps/api/app/services/campaign_service.py` (lines 62-70)

**Problem**: Classic N+1 query - 1 query for campaigns + 1 per campaign for latest run stats

**Solution**: Rewrite with window function subquery and LEFT JOIN

**Impact**: Reduces queries from N+1 to 2

### 2. Admin Import Query Consolidation

**File**: `apps/api/app/services/admin_import_service.py` (lines 238-244)

**Problem**: Two separate queries to User table for ID and email lookups

**Solution**: Single query with OR condition, build both maps from result

**Impact**: 2 queries to 1 (modest improvement for large imports)

### 3. meta_leads Composite Index

**Pre-requisite**: Run EXPLAIN ANALYZE to verify benefit

**Index**:
```sql
CREATE INDEX idx_meta_leads_org_form_converted
ON meta_leads(organization_id, meta_form_id, is_converted);
```

**Note**: Current analytics queries also filter by `coalesce(meta_created_time, received_at)` which this index won't help. Verify actual query patterns first.

---

## Analysis Date

2026-01-22

## Review Methodology

1. Explored database schema via SQLAlchemy models (`apps/api/app/db/models.py`)
2. Analyzed query patterns in service layer (`apps/api/app/services/`)
3. Consulted Supabase postgres-best-practices documentation
4. Validated against existing indexes and constraints
5. Identified blockers and risks for each proposal
