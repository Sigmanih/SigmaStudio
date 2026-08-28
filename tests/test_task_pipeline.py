# ==============================================================================
# tests/test_task_pipeline.py — Unit Tests for Developer Studio Task Pipeline
# ==============================================================================
import pytest
from core.developer_studio.task_pipeline import TaskPipeline, TaskNode, TaskStatus


def test_task_node_creation():
    node = TaskNode(
        id="t1",
        title="Creazione endpoint health",
        role="coder",
        description="Aggiunge GET /api/health",
    )
    assert node.id == "t1"
    assert node.status == TaskStatus.PENDING
    assert not node.is_terminal
    assert node.duration_s is None
    d = node.to_dict()
    assert d["id"] == "t1"
    assert d["status"] == "pending"


def test_pipeline_add_remove_and_dependencies():
    pipe = TaskPipeline(goal="Test Feature")
    n1 = TaskNode(id="1", title="Analisi", role="architect")
    n2 = TaskNode(id="2", title="Branch", role="devops", depends_on=["1"])
    n3 = TaskNode(id="3", title="Codice", role="coder", depends_on=["2"])

    pipe.add_tasks([n1, n2, n3])
    assert len(pipe.nodes) == 3

    # Initially only n1 is ready
    ready = pipe.get_ready_tasks()
    assert len(ready) == 1
    assert ready[0].id == "1"

    # Mark n1 done
    pipe.mark_running("1")
    pipe.mark_done("1", output="Piano completato")
    assert pipe.nodes["1"].status == TaskStatus.DONE

    # Now n2 is ready
    ready = pipe.get_ready_tasks()
    assert len(ready) == 1
    assert ready[0].id == "2"


def test_pipeline_parallel_groups():
    pipe = TaskPipeline(goal="Parallel test")
    n1 = TaskNode(id="1", title="Arch", role="architect")
    n2a = TaskNode(id="2a", title="Code Backend", role="coder", depends_on=["1"])
    n2b = TaskNode(id="2b", title="Code Frontend", role="coder", depends_on=["1"])
    n3 = TaskNode(id="3", title="Test All", role="tester", depends_on=["2a", "2b"])

    pipe.add_tasks([n1, n2a, n2b, n3])
    groups = pipe.get_parallel_groups()

    assert len(groups) == 3
    assert [n.id for n in groups[0]] == ["1"]
    assert set(n.id for n in groups[1]) == {"2a", "2b"}
    assert [n.id for n in groups[2]] == ["3"]


def test_pipeline_retry_and_fix_task():
    pipe = TaskPipeline(goal="Retry test")
    n1 = TaskNode(id="1", title="Task da correggere", role="coder", max_retries=2)
    n2 = TaskNode(id="2", title="Task a valle", role="tester", depends_on=["1"])
    pipe.add_tasks([n1, n2])

    pipe.mark_failed("1", error="SyntaxError")
    assert pipe.nodes["1"].status == TaskStatus.FAILED
    assert pipe.has_failures

    # Retry
    ok = pipe.retry_task("1")
    assert ok
    assert pipe.nodes["1"].retry_count == 1
    assert pipe.nodes["1"].status == TaskStatus.PENDING

    # Insert fix task
    fix = pipe.insert_fix_task("1", "Risolvi SyntaxError")
    assert fix.id in pipe.nodes
    assert fix.id in pipe.nodes["2"].depends_on


def test_pipeline_progress_and_summary():
    pipe = TaskPipeline(goal="Summary test")
    pipe.add_task(TaskNode(id="1", title="T1", role="coder"))
    pipe.add_task(TaskNode(id="2", title="T2", role="coder"))

    assert pipe.progress_percent == 0.0
    pipe.mark_done("1", files_modified=["core/test.py"])
    assert pipe.progress_percent == 50.0

    pipe.mark_done("2", files_modified=["core/another.py"])
    assert pipe.progress_percent == 100.0
    assert pipe.is_complete
    assert set(pipe.get_all_modified_files()) == {"core/test.py", "core/another.py"}
