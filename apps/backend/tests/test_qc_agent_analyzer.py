"""Model output must remain linked to existing evidence and bounded procedures."""

import json
import io
import os
from contextlib import ExitStack, contextmanager
from email.message import Message
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.request
import urllib.response

from modules.test_failures.qc_agent import analyzer


def finding():
    return {
        "finding_id": "F1",
        "category": "right_reference_blocked",
        "status": "needs_confirmation",
        "evidence_refs": ["report_rows[1]"],
        "observed": "右侧参考取头失败，左侧未执行。",
        "checks": ["确认对应吸头盒 A12 是否有吸头，记录实际取头状态。"],
        "direction": "先确认右侧参考取头条件。",
        "retest": "参考成功后复测对应左侧项目。",
    }


def response():
    return {
        "assessments": [
            {
                "finding_id": "F1",
                "priority": 1,
                "reasoning": finding()["observed"],
                "next_question": "请补充检查结果：" + finding()["checks"][0],
                "evidence_refs": ["report_rows[1]"],
            }
        ]
    }


class AnalyzerTests(unittest.TestCase):
    @contextmanager
    def model_transport(self, *, redirect_code=None):
        """Exercise the real opener chain with a final in-memory HTTP transport."""
        requests, configured_handlers = [], []
        real_build_opener = urllib.request.build_opener

        class CapturedHTTPHandler(urllib.request.HTTPHandler):
            def http_open(self, request):
                requests.append(request)
                headers = Message()
                if redirect_code and len(requests) == 1:
                    headers["Location"] = "http://external.invalid/report"
                    code, data = redirect_code, b""
                else:
                    code, data = 200, json.dumps({
                        "done": True, "model": "local-model",
                        "message": {"content": json.dumps(response())},
                    }).encode()
                reply = urllib.response.addinfourl(io.BytesIO(data), headers, request.full_url, code)
                reply.msg = "Found" if code != 200 else "OK"
                return reply

        def build_opener(*handlers):
            configured_handlers.extend(handlers)
            return real_build_opener(*handlers, CapturedHTTPHandler())

        item = finding()
        explanations, questions = analyzer._approved_options(item)
        context = {"findings": [{**item, "explanation_options": explanations, "question_options": questions}]}
        with ExitStack() as patches:
            patches.enter_context(patch.object(analyzer.urllib.request, "build_opener", side_effect=build_opener))
            patches.enter_context(patch.object(analyzer.urllib.request, "urlopen", side_effect=AssertionError("global opener forbidden")))
            patches.enter_context(patch("socket.socket.connect", side_effect=AssertionError("real network forbidden")))
            patches.enter_context(patch.dict(os.environ, {"HTTP_PROXY": "http://proxy.invalid:8080", "http_proxy": "http://proxy.invalid:8080", "NO_PROXY": "", "no_proxy": ""}))
            yield context, requests, configured_handlers

    def test_model_transport_ignores_environment_proxies(self):
        with self.model_transport() as (context, requests, handlers):
            result = analyzer._request_model(context, {})
            self.assertEqual(result["content"], response())
            self.assertEqual([request.full_url for request in requests], ["http://127.0.0.1:11434/api/chat"])
            self.assertFalse(requests[0].has_proxy())
            self.assertEqual([handler.proxies for handler in handlers if isinstance(handler, urllib.request.ProxyHandler)], [{}])

    def test_model_transport_never_follows_redirects(self):
        for code in (301, 302, 303, 307, 308):
            with self.subTest(code=code), self.model_transport(redirect_code=code) as (context, requests, _):
                with self.assertRaisesRegex(analyzer.ModelAnalysisError, "redirects are not permitted"):
                    analyzer._request_model(context, {})
                self.assertEqual(len(requests), 1)

    def test_nonlocal_model_endpoints_are_rejected_before_transport(self):
        with patch.object(analyzer.urllib.request, "build_opener") as opener:
            for endpoint in ("https://localhost:11434", "http://external.invalid", "http://user:pass@127.0.0.1", "http://localhost/other", "http://localhost?forward=external"):
                with self.subTest(endpoint=endpoint), self.assertRaises(analyzer.ModelAnalysisError):
                    analyzer._request_model({}, {"model_base_url": endpoint})
            opener.assert_not_called()

    def test_valid_evidence_reference(self):
        self.assertEqual(
            analyzer._validate_assessments(response(), [finding()])[0]["priority"], 1
        )

    def test_unknown_reference(self):
        result = response()
        result["assessments"][0]["evidence_refs"] = ["report_rows[900]"]
        with self.assertRaises(analyzer.ModelAnalysisError):
            analyzer._validate_assessments(result, [finding()])

    def test_missing_findings(self):
        with self.assertRaises(analyzer.ModelAnalysisError):
            analyzer._validate_assessments({"assessments": []}, [finding()])

    def test_duplicate_findings(self):
        result = response()
        result["assessments"] *= 2
        with self.assertRaises(analyzer.ModelAnalysisError):
            analyzer._validate_assessments(result, [finding()])

    def test_unsupported_repairs_rejected(self):
        for text in (
            "关闭压力保护继续运行",
            "拆卸柱塞检查",
            "更换压力传感器",
            "增大压力阈值",
            "左侧压力传感器已经损坏，建议换新。",
            "成功率达到99%",
        ):
            result = response()
            result["assessments"][0]["reasoning"] = text
            with self.subTest(text=text), self.assertRaises(
                analyzer.ModelAnalysisError
            ):
                analyzer._validate_assessments(result, [finding()])

    def test_model_cannot_supply_procedural_fields(self):
        result = response()
        result["assessments"][0]["checks"] = ["invented action"]
        with self.assertRaises(analyzer.ModelAnalysisError):
            analyzer._validate_assessments(result, [finding()])

    def test_model_failure_does_not_publish_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = {
                "deterministic_findings": [finding()],
                "evidence_catalog": {"report_rows[1]": {"result": "FAIL"}},
            }
            with patch.object(
                analyzer, "prepare_evidence", return_value=evidence
            ), patch.object(
                analyzer,
                "_request_model",
                side_effect=analyzer.ModelAnalysisError("unavailable"),
            ):
                with self.assertRaises(analyzer.ModelAnalysisError):
                    analyzer.analyze_report(root, "report.json", root / "output", {})
            self.assertFalse((root / "output" / "analysis.md").exists())

    def test_output_preserves_rules_and_escapes_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshot = root / "_inputs"
            snapshot.mkdir()
            (snapshot / "report.json").write_text('{"original": true}')
            evidence = {
                "deterministic_findings": [finding()],
                "evidence_catalog": {"report_rows[1]": {"result": "FAIL"}},
                "report_identity": {"serial": "<script>"},
            }
            with patch.object(
                analyzer, "prepare_evidence", return_value=evidence
            ), patch.object(
                analyzer,
                "_request_model",
                return_value={"content": response(), "model": "qwen3:8b"},
            ):
                result = analyzer.analyze_report(snapshot, "report.json", root, {})
            self.assertEqual(result["status"], "complete")
            parsed = json.loads((root / "analysis.json").read_text())
            self.assertEqual(
                parsed["evidence"]["deterministic_findings"][0]["checks"],
                finding()["checks"],
            )
            self.assertIn("report.json", parsed["input_hashes"])
            self.assertNotIn("<script>", (root / "analysis.html").read_text())
            self.assertEqual(
                (snapshot / "report.json").read_text(), '{"original": true}'
            )


if __name__ == "__main__":
    unittest.main()
