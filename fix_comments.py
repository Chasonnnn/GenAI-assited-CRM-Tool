import re

with open("apps/api/app/services/pipeline_service.py", "r") as f:
    content = f.read()

replacement1 = """                # ⚡ Bolt Optimization: Use db.scalar(select(func.count(Model.id)))
                # instead of db.query(Model).count() to avoid inefficient subqueries
                # and directly execute a COUNT aggregate, significantly reducing database CPU load.
                db.scalar(
                    select(func.count(PipelineStage.id)).where(
                        PipelineStage.pipeline_id == pipeline_id
                    )
                )
                or 0"""

content = re.sub(
    r"db\.scalar\(\s*select\(func\.count\(PipelineStage\.id\)\)\.where\(\s*PipelineStage\.pipeline_id == pipeline_id\s*\)\s*\)\s*or 0",
    replacement1,
    content
)


replacement2 = """                # ⚡ Bolt Optimization: Optimized count query to avoid subqueries
                # (reduces database CPU load & execution time).
                db.scalar(
                    select(func.count(IntendedParent.id)).where(
                        IntendedParent.organization_id == pipeline.organization_id,
                        IntendedParent.stage_id == stage.id,
                        IntendedParent.is_archived.is_(False),
                    )
                )
                or 0"""

content = re.sub(
    r"db\.scalar\(\s*select\(func\.count\(IntendedParent\.id\)\)\.where\(\s*IntendedParent\.organization_id == pipeline\.organization_id,\s*IntendedParent\.stage_id == stage\.id,\s*IntendedParent\.is_archived\.is_\(False\),\s*\)\s*\)\s*or 0",
    replacement2,
    content
)


replacement3 = """                # ⚡ Bolt Optimization: Optimized count query to avoid subqueries
                # (reduces database CPU load & execution time).
                db.scalar(
                    select(func.count(Surrogate.id)).where(
                        Surrogate.organization_id == pipeline.organization_id,
                        Surrogate.stage_id == stage.id,
                        Surrogate.is_archived.is_(False),
                    )
                )
                or 0"""

content = re.sub(
    r"db\.scalar\(\s*select\(func\.count\(Surrogate\.id\)\)\.where\(\s*Surrogate\.organization_id == pipeline\.organization_id,\s*Surrogate\.stage_id == stage\.id,\s*Surrogate\.is_archived\.is_\(False\),\s*\)\s*\)\s*or 0",
    replacement3,
    content
)


with open("apps/api/app/services/pipeline_service.py", "w") as f:
    f.write(content)

print("Done")
