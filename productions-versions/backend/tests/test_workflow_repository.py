import json

from workflows.models import Workflow, WorkflowIgnoredPartRule, WorkflowRun
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


def test_ignored_part_rules_are_isolated_by_workflow_and_deleted_with_workflow(tmp_path) -> None:
    repository = WorkflowRepository(tmp_path / "workflows.sqlite3")
    first = repository.save_workflow(Workflow(name="First"))
    second = repository.save_workflow(Workflow(name="Second"))
    repository.save_ignored_part_rule(
        WorkflowIgnoredPartRule(
            workflow_id=first.id,
            part_number="438-00147",
            reason="当前产品不参与核对",
        )
    )
    repository.save_ignored_part_rule(
        WorkflowIgnoredPartRule(
            workflow_id=second.id,
            part_number="438-00147",
            reason="另一个工作流的原因",
        )
    )

    assert repository.list_ignored_part_rules(first.id)[0].reason == "当前产品不参与核对"
    assert repository.list_ignored_part_rules(second.id)[0].reason == "另一个工作流的原因"

    repository.delete_workflow(first.id)

    assert repository.list_ignored_part_rules(first.id) == []
    assert len(repository.list_ignored_part_rules(second.id)) == 1
