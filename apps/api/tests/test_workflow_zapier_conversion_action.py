from __future__ import annotations

from uuid import uuid4

from app.db.enums import JobType, SurrogateSource, WorkflowExecutionStatus, WorkflowTriggerType
from app.db.models import AutomationWorkflow, Job, MetaLead
from app.schemas.surrogate import SurrogateCreate
from app.services import pipeline_service, surrogate_service
from app.services.workflow_engine import engine


def _get_stage(db, org_id, slug: str):
    pipeline = pipeline_service.get_or_create_default_pipeline(db, org_id)
    stage = pipeline_service.get_stage_by_slug(db, pipeline.id, slug)
    assert stage is not None
    return stage


def _create_meta_lead(db, org_id) -> MetaLead:
    lead = MetaLead(
        organization_id=org_id,
        meta_lead_id=f"lead-{uuid4().hex[:8]}",
        meta_form_id="form_1",
        meta_page_id="page_1",
        field_data={"full_name": "Meta Lead", "email": "meta@example.com"},
        field_data_raw={"full_name": "Meta Lead", "email": "meta@example.com"},
    )
    db.add(lead)
    db.commit()
    return lead


def _create_meta_surrogate(db, org_id, user_id):
    surrogate = surrogate_service.create_surrogate(
        db,
        org_id,
        user_id,
        SurrogateCreate(
            full_name="Workflow Zapier Conversion",
            email=f"workflow-zapier-{uuid4().hex[:8]}@example.com",
            source=SurrogateSource.META,
        ),
    )
    return surrogate


def test_status_changed_workflow_send_zapier_conversion_event_queues_job(db, test_org, test_user):
    from app.services import zapier_settings_service

    pre_qualified = _get_stage(db, test_org.id, "pre_qualified")
    lead = _create_meta_lead(db, test_org.id)
    surrogate = _create_meta_surrogate(db, test_org.id, test_user.id)
    surrogate.meta_lead_id = lead.id
    surrogate.meta_form_id = lead.meta_form_id
    surrogate.stage_id = pre_qualified.id
    surrogate.status_label = pre_qualified.label
    db.commit()

    settings = zapier_settings_service.get_or_create_settings(db, test_org.id)
    settings.outbound_webhook_url = "https://hooks.zapier.com/hooks/catch/123/abc"
    settings.outbound_enabled = True
    settings.outbound_event_mapping = [
        {"stage_key": "pre_qualified", "event_name": "Qualified", "enabled": True}
    ]
    db.commit()

    workflow = AutomationWorkflow(
        id=uuid4(),
        organization_id=test_org.id,
        name="Status -> Zapier conversion",
        trigger_type=WorkflowTriggerType.STATUS_CHANGED.value,
        trigger_config={},
        conditions=[],
        condition_logic="AND",
        actions=[{"action_type": "send_zapier_conversion_event"}],
        is_enabled=True,
        is_system_workflow=False,
        created_by_user_id=test_user.id,
    )
    db.add(workflow)
    db.commit()

    executions = engine.trigger(
        db=db,
        trigger_type=WorkflowTriggerType.STATUS_CHANGED,
        entity_type="surrogate",
        entity_id=surrogate.id,
        event_data={
            "old_stage_id": None,
            "new_stage_id": str(pre_qualified.id),
            "old_stage_key": None,
            "new_stage_key": pre_qualified.stage_key,
        },
        org_id=test_org.id,
    )

    assert len(executions) == 1
    assert executions[0].status == WorkflowExecutionStatus.SUCCESS.value
    assert executions[0].actions_executed[0]["action_type"] == "send_zapier_conversion_event"
    assert executions[0].actions_executed[0]["queued"] is True

    job = (
        db.query(Job)
        .filter(
            Job.organization_id == test_org.id,
            Job.job_type == JobType.ZAPIER_STAGE_EVENT.value,
        )
        .order_by(Job.created_at.desc())
        .first()
    )
    assert job is not None
    assert job.payload["data"]["event_name"] == "Qualified"
    assert job.payload["data"]["stage_key"] == "pre_qualified"


def test_status_changed_workflow_send_zapier_conversion_event_skips_when_outbound_disabled(
    db, test_org, test_user
):
    from app.services import zapier_settings_service

    pre_qualified = _get_stage(db, test_org.id, "pre_qualified")
    lead = _create_meta_lead(db, test_org.id)
    surrogate = _create_meta_surrogate(db, test_org.id, test_user.id)
    surrogate.meta_lead_id = lead.id
    surrogate.meta_form_id = lead.meta_form_id
    surrogate.stage_id = pre_qualified.id
    surrogate.status_label = pre_qualified.label
    db.commit()

    settings = zapier_settings_service.get_or_create_settings(db, test_org.id)
    settings.outbound_webhook_url = "https://hooks.zapier.com/hooks/catch/123/abc"
    settings.outbound_enabled = False
    db.commit()

    workflow = AutomationWorkflow(
        id=uuid4(),
        organization_id=test_org.id,
        name="Status -> Zapier conversion disabled",
        trigger_type=WorkflowTriggerType.STATUS_CHANGED.value,
        trigger_config={},
        conditions=[],
        condition_logic="AND",
        actions=[{"action_type": "send_zapier_conversion_event"}],
        is_enabled=True,
        is_system_workflow=False,
        created_by_user_id=test_user.id,
    )
    db.add(workflow)
    db.commit()

    executions = engine.trigger(
        db=db,
        trigger_type=WorkflowTriggerType.STATUS_CHANGED,
        entity_type="surrogate",
        entity_id=surrogate.id,
        event_data={
            "old_stage_id": None,
            "new_stage_id": str(pre_qualified.id),
            "old_stage_key": None,
            "new_stage_key": pre_qualified.stage_key,
        },
        org_id=test_org.id,
    )

    assert len(executions) == 1
    assert executions[0].status == WorkflowExecutionStatus.SUCCESS.value
    assert executions[0].actions_executed[0]["action_type"] == "send_zapier_conversion_event"
    assert executions[0].actions_executed[0]["queued"] is False
    assert executions[0].actions_executed[0]["skipped"] is True
    assert "disabled" in str(executions[0].actions_executed[0]["description"]).lower()

    job = (
        db.query(Job)
        .filter(
            Job.organization_id == test_org.id,
            Job.job_type == JobType.ZAPIER_STAGE_EVENT.value,
        )
        .first()
    )
    assert job is None


def test_status_changed_workflow_send_zapier_conversion_event_skips_new_unread_stage(
    db, test_org, test_user
):
    from app.services import zapier_settings_service

    new_unread = _get_stage(db, test_org.id, "new_unread")
    lead = _create_meta_lead(db, test_org.id)
    surrogate = _create_meta_surrogate(db, test_org.id, test_user.id)
    surrogate.meta_lead_id = lead.id
    surrogate.meta_form_id = lead.meta_form_id
    surrogate.stage_id = new_unread.id
    surrogate.status_label = new_unread.label
    db.commit()

    settings = zapier_settings_service.get_or_create_settings(db, test_org.id)
    settings.outbound_webhook_url = "https://hooks.zapier.com/hooks/catch/123/abc"
    settings.outbound_enabled = True
    settings.outbound_event_mapping = [
        {
            "stage_key": "new_unread",
            "event_name": "Qualified",
            "bucket": "qualified",
            "enabled": True,
        }
    ]
    db.commit()

    workflow = AutomationWorkflow(
        id=uuid4(),
        organization_id=test_org.id,
        name="Status -> Zapier conversion bucket override",
        trigger_type=WorkflowTriggerType.STATUS_CHANGED.value,
        trigger_config={},
        conditions=[],
        condition_logic="AND",
        actions=[{"action_type": "send_zapier_conversion_event"}],
        is_enabled=True,
        is_system_workflow=False,
        created_by_user_id=test_user.id,
    )
    db.add(workflow)
    db.commit()

    executions = engine.trigger(
        db=db,
        trigger_type=WorkflowTriggerType.STATUS_CHANGED,
        entity_type="surrogate",
        entity_id=surrogate.id,
        event_data={
            "old_stage_id": None,
            "new_stage_id": str(new_unread.id),
            "old_stage_key": None,
            "new_stage_key": new_unread.stage_key,
        },
        org_id=test_org.id,
    )

    assert len(executions) == 1
    assert executions[0].status == WorkflowExecutionStatus.SUCCESS.value
    assert executions[0].actions_executed[0]["queued"] is False
    assert executions[0].actions_executed[0]["skipped"] is True
    assert "not mapped" in str(executions[0].actions_executed[0]["description"]).lower()

    job = (
        db.query(Job)
        .filter(
            Job.organization_id == test_org.id,
            Job.job_type == JobType.ZAPIER_STAGE_EVENT.value,
        )
        .order_by(Job.created_at.desc())
        .first()
    )
    assert job is None


def test_status_changed_workflow_conversion_event_fans_out_to_zapier_and_meta_dataset(
    db, test_org, test_user
):
    from app.services import meta_crm_dataset_settings_service, zapier_settings_service

    pre_qualified = _get_stage(db, test_org.id, "pre_qualified")
    lead = _create_meta_lead(db, test_org.id)
    surrogate = _create_meta_surrogate(db, test_org.id, test_user.id)
    surrogate.meta_lead_id = lead.id
    surrogate.meta_form_id = lead.meta_form_id
    surrogate.stage_id = pre_qualified.id
    surrogate.status_label = pre_qualified.label
    db.commit()

    zapier_settings = zapier_settings_service.get_or_create_settings(db, test_org.id)
    zapier_settings.outbound_webhook_url = "https://hooks.zapier.com/hooks/catch/123/abc"
    zapier_settings.outbound_enabled = True
    zapier_settings.outbound_event_mapping = [
        {"stage_key": "pre_qualified", "event_name": "Qualified", "enabled": True}
    ]

    meta_settings = meta_crm_dataset_settings_service.get_or_create_settings(db, test_org.id)
    meta_settings.dataset_id = "1428122951556949"
    meta_settings.access_token_encrypted = meta_crm_dataset_settings_service.encrypt_access_token(
        "meta-token"
    )
    meta_settings.enabled = True
    meta_settings.crm_name = "Surrogacy Force CRM"
    meta_settings.event_mapping = [
        {"stage_key": "pre_qualified", "event_name": "Qualified", "enabled": True}
    ]
    db.commit()

    workflow = AutomationWorkflow(
        id=uuid4(),
        organization_id=test_org.id,
        name="Status -> all conversion transports",
        trigger_type=WorkflowTriggerType.STATUS_CHANGED.value,
        trigger_config={},
        conditions=[],
        condition_logic="AND",
        actions=[{"action_type": "send_zapier_conversion_event"}],
        is_enabled=True,
        is_system_workflow=False,
        created_by_user_id=test_user.id,
    )
    db.add(workflow)
    db.commit()

    executions = engine.trigger(
        db=db,
        trigger_type=WorkflowTriggerType.STATUS_CHANGED,
        entity_type="surrogate",
        entity_id=surrogate.id,
        event_data={
            "old_stage_id": None,
            "new_stage_id": str(pre_qualified.id),
            "old_stage_key": None,
            "new_stage_key": pre_qualified.stage_key,
        },
        org_id=test_org.id,
    )

    assert len(executions) == 1
    assert executions[0].status == WorkflowExecutionStatus.SUCCESS.value
    assert executions[0].actions_executed[0]["queued"] is True
    assert executions[0].actions_executed[0]["transport_results"]["zapier"]["queued"] is True
    assert (
        executions[0].actions_executed[0]["transport_results"]["meta_crm_dataset"]["queued"] is True
    )

    assert (
        db.query(Job)
        .filter(
            Job.organization_id == test_org.id,
            Job.job_type == JobType.ZAPIER_STAGE_EVENT.value,
        )
        .count()
        == 1
    )
    assert (
        db.query(Job)
        .filter(
            Job.organization_id == test_org.id,
            Job.job_type == JobType.META_CRM_DATASET_EVENT.value,
        )
        .count()
        == 1
    )
