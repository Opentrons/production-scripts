import json

from workflows.models import Workflow, WorkflowRun
from workflows.repository import WorkflowRepository


def test_repository_migrates_legacy_json_to_sqlite(tmp_path) -> None:
    workflow = Workflow(name="Legacy workflow")
    run = WorkflowRun(
        workflow_id=workflow.id,
        workflow_name=workflow.name,
        trigger_type="manual",
    )
    legacy_path = tmp_path / "workflows.json"
    legacy_path.write_text(
        json.dumps(
            {
                "workflows": [workflow.model_dump(mode="json")],
                "runs": [run.model_dump(mode="json")],
            }
        ),
        encoding="utf-8",
    )

    repository = WorkflowRepository(
        tmp_path / "workflows.sqlite3",
        legacy_json_path=legacy_path,
    )

    assert repository.get_workflow(workflow.id) == workflow
    assert repository.list_runs(workflow_id=workflow.id)[0] == run


def test_list_workflows_includes_run_count(tmp_path) -> None:
    repository = WorkflowRepository(tmp_path / "workflows.sqlite3")
    workflow = repository.save_workflow(Workflow(name="Counted workflow"))
    repository.save_run(WorkflowRun(workflow_id=workflow.id, workflow_name=workflow.name, trigger_type="manual"))
    repository.save_run(WorkflowRun(workflow_id=workflow.id, workflow_name=workflow.name, trigger_type="scheduled"))

    listed = repository.list_workflows()[0]

    assert listed.run_count == 2
