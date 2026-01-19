import uuid

from app.db.models import Pipeline, Queue
from app.services import org_service


def test_create_org_seeds_pipeline_and_queues(db):
    slug = f"seed-org-{uuid.uuid4().hex[:8]}"

    org = org_service.create_org(db, name="Seed Org", slug=slug)

    pipeline = (
        db.query(Pipeline)
        .filter(Pipeline.organization_id == org.id, Pipeline.is_default.is_(True))
        .first()
    )
    assert pipeline is not None

    queue_names = {
        queue.name
        for queue in db.query(Queue)
        .filter(Queue.organization_id == org.id, Queue.is_active.is_(True))
        .all()
    }
    assert "Unassigned" in queue_names
    assert "Surrogate Pool" in queue_names
