"""Stage 7: actual CU/emart24 main() paths, all I/O patched and synthetic.

Run from repo root. No production state files, inventory APIs, Telegram, or
GitHub calls. The caller persists the returned synthetic outbox in a test branch.
"""
import contextlib
import io
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import cu_stock_monitor as cu
import monitor as em
from experiments.isolated_state_outbox import queue_transition


def scan_synthetic():
    result = {"synthetic": True, "telegram_calls": 0, "chains": {}}
    with tempfile.TemporaryDirectory(prefix="stage7-fake-state-") as tmp:
        root = Path(tmp)
        # Real CU main(), with one synthetic observed store and fake send.
        cu_file = root / "cu_stock_state.json"
        cu_file.write_text(json.dumps({"stores": {}}))
        cu_item = {"code": "FAKE-CU-01", "name": "테스트점",
                   "address": "충청남도 아산시 테스트로 12",
                   "city": "아산", "stock": 3}
        cu_messages = []
        with patch.object(cu, "STATE_FILE", cu_file), \
             patch.object(cu, "POINTS", {"아산": [(36.79, 127.0)]}), \
             patch.object(cu, "query", return_value=[cu_item]), \
             patch.object(cu, "telegram", side_effect=lambda msg: cu_messages.append(msg) or True), \
             patch("unified_settings.enabled", return_value={"asan"}), \
             patch("cu_asan_registry.summarize_observations", return_value=None), \
             contextlib.redirect_stdout(io.StringIO()):
            cu.main()
        assert len(cu_messages) == 0
        cu_state = json.loads(cu_file.read_text())
        assert cu_state["stores"]["FAKE-CU-01"]["stock"] == 3
        # Scanner's Telegram is replaced by capture only. Convert captured
        # message to pending event, never deliver it.
        assert len(cu_state["pending_alerts"]) == 1
        eid = next(iter(cu_state["pending_alerts"]))
        state = cu_state
        result["chains"]["cu"] = {"state": state, "eid": eid}

        # Real emart24 main(), with synthetic store discovery and stock().
        em_state_file = root / "state.json"
        em_store_file = root / "stores.json"
        em_state_file.write_text("{}")
        em_store_file.write_text("{}")
        fake_stores = {"FAKE-EM-01": {"name": "가상점",
                                     "address": "충청남도 아산시 테스트로 20"}}
        em_messages = []
        with patch.object(em, "STATE_FILE", em_state_file), \
             patch.object(em, "STORES_FILE", em_store_file), \
             patch.object(em, "get_stores", return_value=fake_stores), \
             patch.object(em, "stock", return_value=({"FAKE-EM-01": 4}, {"FAKE-EM-01": "OK"})), \
             patch.object(em, "notify", side_effect=lambda msg: em_messages.append(msg) or True), \
             patch("unified_settings.enabled", return_value={"asan"}), \
             contextlib.redirect_stdout(io.StringIO()):
            em.main()
        assert len(em_messages) == 0
        em_state = json.loads(em_state_file.read_text())
        assert em_state["이마트24|FAKE-EM-01|8800286275732"] == 4
        assert len(em_state["pending_alerts"]) == 1
        eid = next(iter(em_state["pending_alerts"]))
        state = em_state
        result["chains"]["emart24"] = {"state": state, "eid": eid}
    assert result["telegram_calls"] == 0
    return result


if __name__ == "__main__":
    print(json.dumps(scan_synthetic(), ensure_ascii=False, indent=2))
