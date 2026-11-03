## 2024-05-19 - Vectorize MedicalRecord N+1 queries during form mapping

**Learning:** When `apply_form_values` applies incoming form data to medical records, it iterated over form sections and queried the database individually for the current record of each section using `_load(db, owner, section=section)`. This resulted in N+1 database queries, scaling with the number of sections being updated.

**Action:** Optimized `apply_form_values` to fetch all medical records for the owner in a single query outside the loop using `_load(db, owner, lock=True)`. Then mapped these records into an in-memory dictionary grouped by section for O(1) lookups during the loop, eliminating the N+1 problem.
