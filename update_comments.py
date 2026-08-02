import re

with open('apps/api/app/services/form_intake_service.py', 'r') as f:
    content = f.read()

old_version = """    version_number = (
        db.scalar(
            select(func.count(PublishedIntakeVersion.id))
            .where(PublishedIntakeVersion.intake_link_id == link.id)
        )
        or 0
    ) + 1"""

new_version = """    # Performance: Use db.scalar(select(func.count(...))) instead of query.count()
    # to avoid wrapping the query in an inefficient subquery (e.g., SELECT count(*) FROM (SELECT ...))
    # and to directly compute the aggregate.
    version_number = (
        db.scalar(
            select(func.count(PublishedIntakeVersion.id))
            .where(PublishedIntakeVersion.intake_link_id == link.id)
        )
        or 0
    ) + 1"""

content = content.replace(old_version, new_version)

old_linked = """            linked_count = (
                db.scalar(
                    select(func.count(FormSubmission.id))
                    .where(
                        FormSubmission.intake_lead_id == lead.id,
                        FormSubmission.surrogate_id == surrogate.id,
                    )
                )
                or 0
            )"""

new_linked = """            # Performance: Direct aggregate calculation to prevent SQLAlchemy subquery overhead.
            linked_count = (
                db.scalar(
                    select(func.count(FormSubmission.id))
                    .where(
                        FormSubmission.intake_lead_id == lead.id,
                        FormSubmission.surrogate_id == surrogate.id,
                    )
                )
                or 0
            )"""

content = content.replace(old_linked, new_linked)

with open('apps/api/app/services/form_intake_service.py', 'w') as f:
    f.write(content)
