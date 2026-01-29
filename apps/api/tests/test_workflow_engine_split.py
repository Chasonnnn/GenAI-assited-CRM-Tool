def test_workflow_engine_split_modules_exist():
    import importlib

    core_module = importlib.import_module("app.services.workflow_engine_core")
    adapter_module = importlib.import_module("app.services.workflow_engine_adapters")
    engine_module = importlib.import_module("app.services.workflow_engine")

    assert hasattr(core_module, "WorkflowEngineCore")
    assert hasattr(adapter_module, "WorkflowDomainAdapter")
    assert hasattr(adapter_module, "DefaultWorkflowDomainAdapter")
    assert hasattr(engine_module, "engine")
