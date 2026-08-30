import uuid

from app.db.models import Pipeline, Queue
from app.services import org_service


def test_create_org_seeds_pipeline_and_queues(db):
    slug = f"seed-org-{uuid.uuid4().hex[:8]}"

    org = org_service.create_org(db, name="Seed Org", slug=slug)

    pipelines = (
        db.query(Pipeline)
        .filter(Pipeline.organization_id == org.id, Pipeline.is_default.is_(True))
        .all()
    )
    pipelines_by_type = {pipeline.entity_type: pipeline for pipeline in pipelines}
    assert {"surrogate", "egg_donor", "sperm_donor"}.issubset(pipelines_by_type)
    assert len(pipelines_by_type["egg_donor"].stages) == 13
    assert len(pipelines_by_type["sperm_donor"].stages) == 13
    assert pipelines_by_type["egg_donor"].id != pipelines_by_type["sperm_donor"].id

    queue_names = {
        queue.name
        for queue in db.query(Queue)
        .filter(Queue.organization_id == org.id, Queue.is_active.is_(True))
        .all()
    }
    assert "Unassigned" in queue_names
    assert "Surrogate Pool" in queue_names
