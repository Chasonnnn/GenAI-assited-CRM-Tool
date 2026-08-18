## 2024-08-18 - Replacing N+1 ORM updates with bulk updates
**Learning:** Found an anti-pattern where a loop iterates over `db.scalars(select(...)).all()` and modifies a field on each item individually.
**Action:** Replace `for item in db.scalars...: item.field = value` with `db.execute(update(Model).where(...).values(field=value))` to eliminate N+1 roundtrips.
