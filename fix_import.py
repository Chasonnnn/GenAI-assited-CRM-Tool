with open("apps/api/app/services/admin_import_service.py", "r") as f:
    text = f.read()

text = text.replace("select(func.count(MetaPageMapping.id))", "select(func.count(MetaPageMapping.page_id))")

with open("apps/api/app/services/admin_import_service.py", "w") as f:
    f.write(text)
