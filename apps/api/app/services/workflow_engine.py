"""Workflow engine facade using the core engine + default domain adapter."""

from app.services.workflow_engine_adapters import DefaultWorkflowDomainAdapter
from app.services.workflow_engine_core import WorkflowEngineCore


class WorkflowEngine(WorkflowEngineCore):
    def __init__(self) -> None:
        super().__init__(DefaultWorkflowDomainAdapter())


# Singleton instance
engine = WorkflowEngine()
