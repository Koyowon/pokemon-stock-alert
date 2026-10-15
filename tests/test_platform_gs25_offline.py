"""Offline tests for GitHub artifact provenance and GS25 partial scan semantics."""
import importlib.util
import io
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from state_artifact_platform import validate_platform_artifact

ROOT = Path(__file__).resolve().parent.parent


class FakeResponse:
    def __init__(self, payload):
        self.data = json.dumps(payload).encode()
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self):
        return self.data


class PlatformTests(unittest.TestCase):
    def test_valid_github_artifact_metadata(self):
        digest = "sha256:" + "a" * 64
        info = dict(id=42, name="chain-cu-123-1", digest=digest, expired=False,
                    workflow_run={"id": 123})
        def open_mock(req, timeout):
            self.assertIn("/actions/artifacts/42", req.full_url)
            return FakeResponse(info)
        self.assertTrue(validate_platform_artifact(42, digest, 123,
            "chain-cu-123-1", "fake-token", opener=open_mock))

    def test_rejects_forged_id_digest_run_and_expiry(self):
        digest = "sha256:" + "a" * 64
        good = dict(id=42, name="chain-cu-123-1", digest=digest, expired=False,
                    workflow_run={"id": 123})
        for mutation in ({"id": 43}, {"digest": "sha256:" + "b"*64},
                         {"workflow_run": {"id": 999}}, {"expired": True},
                         {"name": "chain-cu-999-1"}):
            info = {**good, **mutation}
            with self.subTest(mutation=mutation):
                with self.assertRaisesRegex(ValueError, "provenance/digest mismatch"):
                    validate_platform_artifact(42, digest, 123,
                        "chain-cu-123-1", "fake-token",
                        opener=lambda req, timeout: FakeResponse(info))

    def test_workflow_uses_actual_platform_check(self):
        for path in (".github/workflows/stock-monitor.yml",
                     ".github/workflows/cu-stock-monitor.yml",
                     ".github/workflows/gs25-stock-monitor.yml"):
            text = (ROOT / path).read_text()
            self.assertIn("actions: read", text)
            self.assertIn("validate_platform_artifact(", text)
            self.assertIn("merge-multiple: true", text)


class GS25PartialTests(unittest.TestCase):
    def test_completed_region_committed_on_other_region_failure(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            config = root / "config.json"
            state = root / "state.json"
            config.write_text(json.dumps({
                "provider": "GS25", "item_code": "12345678",
                "regions": [{"id": "namwon", "name": "Namwon", "enabled": True},
                            {"id": "jeonju", "name": "Jeonju", "enabled": True}]
            }))
            state.write_text(json.dumps({"version": 2, "item_code": "12345678",
                "regions": {"namwon": {"stores": {"N1": {"name": "Old", "quantity": 1}}},
                            "jeonju": {"stores": {"J1": {"name": "Old", "quantity": 1}}}}}))
            spec = importlib.util.spec_from_file_location("gs25_partial_offline",
                ROOT / "gs25_independent/gs25_auto_monitor.py")
            module = importlib.util.module_from_spec(spec)
            sys.path.insert(0, str(ROOT / "gs25_independent"))
            try:
                spec.loader.exec_module(module)
            finally:
                sys.path.remove(str(ROOT / "gs25_independent"))
            module.CONFIG, module.STATE = config, state
            module.KEYWORDS = {"namwon": ["ok"], "jeonju": ["fail"]}
            fake_settings = types.ModuleType("unified_settings")
            fake_settings.enabled = lambda chain, regions: regions
            alerts = []
            def fake_query(code, term):
                if term == "fail":
                    raise RuntimeError("HTTP_502")
                return [{"storeCode": "N1", "storeName": "Old",
                         "realStockQuantity": 3}]
            with patch.dict(sys.modules, {"unified_settings": fake_settings}), \
                 patch.object(module, "api_query", side_effect=fake_query), \
                 patch.object(module, "telegram", side_effect=alerts.append):
                self.assertEqual(module.main(), 0)
            saved = json.loads(state.read_text())
            self.assertEqual(saved["regions"]["namwon"]["stores"]["N1"]["quantity"], 3)
            self.assertEqual(saved["regions"]["jeonju"]["stores"]["J1"]["quantity"], 1)
            self.assertEqual(len(alerts), 0)
            self.assertEqual(len(saved['pending_alerts']), 1)
            # Repeated successful observation should not enqueue a duplicate.
            module.KEYWORDS = {"namwon": ["ok"], "jeonju": ["ok2"]}
            with patch.dict(sys.modules, {"unified_settings": fake_settings}), \
                 patch.object(module, "api_query", side_effect=lambda code, term: [
                    {"storeCode": "N1", "storeName": "Old", "realStockQuantity": 3}]
                    if term == "ok" else []), \
                 patch.object(module, "telegram", side_effect=alerts.append):
                self.assertEqual(module.main(), 0)
            self.assertEqual(len(alerts), 0)
            self.assertEqual(len(json.loads(state.read_text())['pending_alerts']), 1)


if __name__ == "__main__":
    unittest.main()
