## 2024-05-24 - Missing escape characters in SQLAlchemy ilike query
**Vulnerability:** SQLAlchemy ilike statements without an explicit escape="\\" parameter are vulnerable to SQL wildcard injection if the underlying SQL compiler does not automatically enforce it or if a user inputs % or _ characters.
**Learning:** Some ilike instances in the codebase were not passing the escape="\\" parameter despite passing the escaped string.
**Prevention:** Always include the escape="\\" argument when using SQLAlchemy ilike queries with escaped wildcard inputs.
