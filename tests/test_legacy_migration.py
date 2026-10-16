import copy
import unittest
from cu_emart24_legacy_migration import migrate,verify,rollback_snapshot,check_legacy

COMMIT="a"*40
BLOBS={path:char*40 for path,char in [
    ("cu_stock_state.json","b"),("state.json","c"),("stores.json","d")]}

class LegacyMigrationAcceptance(unittest.TestCase):
    def setUp(self):
        self.source={
            "cu_stock_state.json":{"stores":{
                "11258":{"name":"제주연동중앙점","address":"제주","city":"제주","stock":0,"alerted":False},
                "11704":{"name":"제주은남점","address":"제주","city":"제주","stock":2,"alerted":True},
                "11800":{"name":"미확인점","address":"제주","city":"제주","stock":None,"alerted":False}}},
            "state.json":{"emart24|21598|8809945338207":0,"이마트24|06620|8809945338207":4},
            "stores.json":{"last_refresh":"2026-10-16","stores":{"20365":{"name":"아산음봉쌍암점","address":"아산"}}}}
    def test_exact_legacy_preservation_and_empty_outbox(self):
        original=copy.deepcopy(self.source)
        staged,manifest=migrate(self.source,COMMIT,BLOBS)
        self.assertEqual(self.source,original)
        self.assertTrue(verify(original,staged,manifest))
        self.assertEqual(staged["cu_stock_state.json"]["stores"],original["cu_stock_state.json"]["stores"])
        self.assertEqual(staged["state.json"]["이마트24|06620|8809945338207"],4)
        self.assertEqual(staged["stores.json"],original["stores.json"])
        for path in ("cu_stock_state.json","state.json"):
            self.assertEqual(staged[path]["pending_alerts"],{})
            self.assertEqual(staged[path]["alert_sequence"],0)
        self.assertTrue(manifest["requires_operator_reconciliation"])
        self.assertFalse(manifest["historical_telegram_delivery_inferred"])
    def test_tamper_and_missing_file_fail_closed(self):
        staged,manifest=migrate(self.source,COMMIT,BLOBS)
        staged["cu_stock_state.json"]["stores"]["11704"]["alerted"]=False
        with self.assertRaises(ValueError):verify(self.source,staged,manifest)
        missing=copy.deepcopy(self.source)
        del missing["stores.json"]
        with self.assertRaises(ValueError):check_legacy(missing)
    def test_no_duplicate_initial_alert_created_and_rollback(self):
        staged,manifest=migrate(self.source,COMMIT,BLOBS)
        self.assertEqual(staged["cu_stock_state.json"]["pending_alerts"],{})
        self.assertEqual(staged["state.json"]["pending_alerts"],{})
        self.assertEqual(rollback_snapshot(self.source,manifest),self.source)
        modified=copy.deepcopy(self.source)
        modified["state.json"]["이마트24|06620|8809945338207"]=0
        with self.assertRaises(ValueError):rollback_snapshot(modified,manifest)
    def test_existing_outbox_must_not_be_reset(self):
        bad=copy.deepcopy(self.source)
        bad["state.json"]["pending_alerts"]={"e":{"status":"claimed"}}
        with self.assertRaises(ValueError):migrate(bad,COMMIT,BLOBS)
if __name__=="__main__":unittest.main()
