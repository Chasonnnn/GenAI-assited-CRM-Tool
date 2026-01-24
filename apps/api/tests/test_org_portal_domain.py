import uuid

from app.services import org_service


def test_build_portal_domain_prefixes_base():
    assert org_service.build_portal_domain("ewifamilyglobal.com") == "ap.ewifamilyglobal.com"


def test_build_portal_domain_accepts_prefixed_domain():
    assert org_service.build_portal_domain("ap.ewifamilyglobal.com") == "ap.ewifamilyglobal.com"


def test_create_org_sets_portal_domain(db):
    slug = f"portal-org-{uuid.uuid4().hex[:8]}"
    domain = f"ap.test-{uuid.uuid4().hex[:8]}.com"

    org = org_service.create_org(db, name="Portal Org", slug=slug, portal_domain=domain)

    assert org.portal_domain == domain
