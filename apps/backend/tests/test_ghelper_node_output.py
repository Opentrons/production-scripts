from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "ghelper-test" / "node_test.py"
SPEC = importlib.util.spec_from_file_location("ghelper_node_test", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
node_test = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = node_test
SPEC.loader.exec_module(node_test)


def test_print_results_only_prints_availability_summary(capsys) -> None:
    results = [
        node_test.TestResult(name="available-1", proxy_url="http://proxy-1", success=True),
        node_test.TestResult(name="unavailable-1", proxy_url="http://proxy-2", success=False),
        node_test.TestResult(name="available-2", proxy_url="http://proxy-3", success=True),
    ]

    node_test.print_results(results)

    assert capsys.readouterr().out == "Available nodes: 2, unavailable nodes: 1\n"


def test_run_tests_does_not_print_each_node(monkeypatch, capsys) -> None:
    nodes = [
        node_test.ProxyNode("node-1", "proxy-1", 80, "", "", "http", False),
        node_test.ProxyNode("node-2", "proxy-2", 80, "", "", "http", False),
    ]

    def fake_test_node(node, *, test_url):
        return node_test.TestResult(
            name=node.name,
            proxy_url=node_test.build_proxy_url(node),
            latency=10.0 if node.name == "node-1" else None,
            success=node.name == "node-1",
            error=None if node.name == "node-1" else "unavailable",
        )

    monkeypatch.setattr(node_test, "test_node", fake_test_node)

    results = node_test.run_tests(nodes, max_threads=1)

    assert len(results) == 2
    assert capsys.readouterr().out == ""
