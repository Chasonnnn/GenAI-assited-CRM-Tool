"""Large JSONB columns that ordinary loads never read stay out of entity SELECTs."""

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.db.models import CampaignRecipient, Surrogate


@pytest.mark.parametrize(
    ("model", "column"),
    [(Surrogate, "import_metadata"), (CampaignRecipient, "donor_launch_snapshot")],
)
def test_entity_select_omits_deferred_jsonb(model, column):
    sql = str(select(model).compile(dialect=postgresql.dialect()))
    assert f"{model.__tablename__}.id" in sql
    assert column not in sql
