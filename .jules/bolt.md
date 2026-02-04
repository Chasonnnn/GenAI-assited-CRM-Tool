## 2024-05-22 - [Double Fetching in Serialization]
**Learning:** `_surrogate_to_read` serialization helper was making redundant DB queries to fetch owners (User/Queue) even when the relationships were already eager loaded on the model instance. This caused 1 extra query per single-record fetch and negated the benefit of eager loading.
**Action:** Always check if a relationship is populated on the SQLAlchemy model (e.g., `if instance.rel:`) before falling back to a service call to fetch it.
