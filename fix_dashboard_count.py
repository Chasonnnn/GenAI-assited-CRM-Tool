with open('apps/api/app/services/dashboard_service.py', 'r') as f:
    content = f.read()

# Make sure we didn't duplicate the outerjoin
if content.count('outerjoin(\n            latest_change_subquery') > 2:
    print("Warning: Might have duplicated outerjoins in dashboard_service.py")

with open('apps/api/app/services/intelligent_suggestions_service.py', 'r') as f:
    content2 = f.read()

print("Files rewritten successfully.")
