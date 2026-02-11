import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4
from datetime import datetime

from app.db.enums import OwnerType, Role
from app.routers.surrogates_write import bulk_assign_surrogates
from app.schemas.auth import UserSession
from app.schemas.surrogate import BulkAssign


class TestBulkAssignOptimization(unittest.TestCase):
    def test_bulk_assign_fetches_surrogates_once(self):
        # Setup
        org_id = uuid4()
        user_id = uuid4()
        session = UserSession(
            user_id=user_id,
            org_id=org_id,
            role=Role.ADMIN,
            session_id=uuid4(),
            expires_at=int(datetime.now().timestamp() + 3600),
            email="test@example.com",
            display_name="Test User",
        )
        db = MagicMock()

        target_user_id = uuid4()
        surrogate_ids = [uuid4(), uuid4(), uuid4()]

        data = BulkAssign(
            surrogate_ids=surrogate_ids, owner_type=OwnerType.USER, owner_id=target_user_id
        )

        # Mocks
        with (
            patch("app.routers.surrogates_write.surrogate_service") as mock_surrogate_service,
            patch("app.routers.surrogates_write.membership_service") as mock_membership_service,
        ):
            # Mock membership check passing
            mock_membership_service.get_membership_for_org.return_value = True

            # Mock get_surrogates_by_ids returning objects
            mock_surrogates = [MagicMock(id=sid) for sid in surrogate_ids]
            mock_surrogate_service.get_surrogates_by_ids.return_value = mock_surrogates

            # Execute
            bulk_assign_surrogates(data, session, db)

            # Verify get_surrogates_by_ids called once
            mock_surrogate_service.get_surrogates_by_ids.assert_called_once_with(
                db, org_id, surrogate_ids
            )

            # Verify assign_surrogate called for each surrogate
            assert mock_surrogate_service.assign_surrogate.call_count == 3

            # Verify get_surrogate was NOT called (old method)
            mock_surrogate_service.get_surrogate.assert_not_called()
