with open("apps/api/app/services/admin_import_service.py", "r") as f:
    content = f.read()

# Replace func.count(UserNotificationSettings.id) with func.count(UserNotificationSettings.user_id)
# since UserNotificationSettings doesn't have an `id` field.
content = content.replace("func.count(UserNotificationSettings.id)", "func.count(UserNotificationSettings.user_id)")

with open("apps/api/app/services/admin_import_service.py", "w") as f:
    f.write(content)
