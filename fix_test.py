with open('apps/api/tests/test_dashboard.py', 'r') as f:
    content = f.read()

# The test asserts the old query structure ('exists' and 'not exists')
# We need to change it to assert the new structure ('group by' and 'left outer join' or similar)
content = content.replace(
'''        assert "exists" in combined_sql
        assert "not (" in combined_sql or "not exists" in combined_sql
        assert "group by surrogate_status_history.surrogate_id" not in combined_sql''',
'''        assert "group by surrogate_status_history.surrogate_id" in combined_sql
        assert "outer join" in combined_sql
        assert "exists" not in combined_sql'''
)

with open('apps/api/tests/test_dashboard.py', 'w') as f:
    f.write(content)
