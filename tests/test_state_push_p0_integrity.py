"""P0 integrity checks for candidate publisher. Local temporary bare Git only."""
import hashlib
import json
import unittest
from pathlib import Path

from test_state_push_retry_candidate import CandidatePatchTests
from state_push_retry_candidate import publish, publish_bundle

class P0BundleTests(CandidatePatchTests):
    def test_05_emart24_paired_state_and_cache(self):
        client = self.clone("paired")
        publish_bundle(client, {
            "state.json": self.artifact("state", {"qty": 4}),
            "stores.json": self.artifact("stores", {"stores": {"1": {"name": "test"}}}),
        }, self.base)
        verifier = self.clone("paired_verify")
        self.assertEqual(json.loads((verifier / "state.json").read_text()), {"qty": 4})
        self.assertEqual(json.loads((verifier / "stores.json").read_text()),
                         {"stores": {"1": {"name": "test"}}})

    def test_06_no_change_does_not_push(self):
        client = self.clone("unchanged")
        old = self.g(client, "rev-parse", "HEAD").stdout.strip()
        attempts = publish(client, "cu_stock_state.json",
                           self.artifact("same", {"initial": 1}), self.base)
        self.assertEqual(attempts, 1)
        self.assertEqual(self.g(client, "rev-parse", "HEAD").stdout.strip(), old)

    def test_07_invalid_json_and_checksum_rejected(self):
        client = self.clone("invalid")
        bad = self.root / "invalid.json"
        bad.write_text('{"truncated":', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "invalid JSON"):
            publish(client, "cu_stock_state.json", bad, self.base)
        good = self.artifact("valid", {"ok": 1})
        with self.assertRaisesRegex(ValueError, "checksum"):
            publish_bundle(client, {"cu_stock_state.json": good}, self.base,
                           expected_digests={"cu_stock_state.json": "0" * 64})
        self.assertEqual(self.snapshot()["cu"], {"initial": 1})

    def test_08_reject_missing_symlink_and_wrong_chain_bundle(self):
        client = self.clone("wrong")
        missing = self.root / "missing.json"
        with self.assertRaises(ValueError):
            publish(client, "cu_stock_state.json", missing, self.base)
        symlink = self.root / "link.json"
        symlink.symlink_to(self.artifact("linked", {"ok": 1}))
        with self.assertRaises(ValueError):
            publish(client, "cu_stock_state.json", symlink, self.base)
        with self.assertRaises(ValueError):
            publish_bundle(client, {
                "cu_stock_state.json": self.artifact("cu", {"ok": 1}),
                "gs25_independent/gs25_stock_state.json": self.artifact("gs", {"ok": 1})
            }, self.base)

    def test_09_same_chain_race_rejected(self):
        client = self.clone("same_chain_race")
        def competing(attempt):
            if attempt == 1:
                self.push_chain("cu", 123)
        with self.assertRaisesRegex(RuntimeError, "stale overwrite"):
            publish(client, "cu_stock_state.json",
                    self.artifact("cu_race", {"cu": 2}), self.base,
                    before_push=competing)
        self.assertEqual(self.snapshot()["cu"], {"cu": 123})

    def test_10_reject_incomplete_emart24_bundle(self):
        client = self.clone("partial_em")
        with self.assertRaisesRegex(ValueError, "requires state.json and stores.json"):
            publish(client, "state.json", self.artifact("em", {"qty": 1}), self.base)
        with self.assertRaises(ValueError):
            publish_bundle(client, {"stores.json": self.artifact("cache", {"stores": {}})}, self.base)

if __name__ == "__main__":
    unittest.main()
