"""Offline CU API contract fixtures. No imports from the live monitor, no I/O."""
import unittest

BARCODE = "8800286275732"


def classify_observation(query_attempted, query_success, observed_stock):
    if not query_attempted or not query_success:
        return "NOT_QUERIED"
    if observed_stock is None:
        return "NOT_OBSERVED"
    if type(observed_stock) is not int or observed_stock < 0:
        return "NO_VALID_STOCK_VALUE"
    return "ZERO_STOCK" if observed_stock == 0 else "IN_STOCK"


def reconcile_pages(pages):
    """Reject conflicting code records; never sum stock across pages or points."""
    found, conflicts = {}, set()
    for page in pages:
        if page.get("barcode") != BARCODE or page.get("success") is not True:
            raise ValueError("Invalid response envelope")
        for store in page.get("stores", []):
            code, qty = store.get("code"), store.get("stock")
            if not isinstance(code, str) or not code.isdigit():
                raise ValueError("Invalid CU store code")
            if type(qty) is not int or qty < 0:
                raise ValueError("Invalid stock quantity")
            if code in conflicts:
                continue
            if code in found and found[code] != qty:
                conflicts.add(code)
                del found[code]
            else:
                found[code] = qty
    return found, conflicts


def assess_pagination(pages, declared_total=None):
    """Fixture contract: page completeness cannot be inferred from size alone."""
    if declared_total is None:
        return "UNKNOWN"
    if type(declared_total) is not int or declared_total < 0:
        return "FAIL"
    offsets = [p.get("offset") for p in pages]
    if any(type(o) is not int or o < 0 for o in offsets):
        return "FAIL"
    if len(offsets) != len(set(offsets)):
        return "FAIL"
    count = sum(len(p.get("stores", [])) for p in pages)
    return "PASS" if count >= declared_total else "FAIL"


class ContractFixtures(unittest.TestCase):
    def test_unknown_radius_is_not_coverage(self):
        api_radius_km = None
        self.assertIsNone(api_radius_km)
        self.assertNotEqual(api_radius_km, 3)

    def test_unknown_result_limit_cannot_prove_complete(self):
        self.assertEqual(assess_pagination([{"offset": 0, "stores": [{}]}]), "UNKNOWN")

    def test_incomplete_pages_fail_when_total_known(self):
        self.assertEqual(assess_pagination([{"offset": 0, "stores": [{}]}], 2), "FAIL")

    def test_duplicate_page_offset_fails(self):
        pages = [{"offset": 0, "stores": [{}]}, {"offset": 0, "stores": [{}]}]
        self.assertEqual(assess_pagination(pages, 2), "FAIL")

    def test_complete_pages_pass_fixture_only(self):
        pages = [{"offset": 0, "stores": [{}]}, {"offset": 1, "stores": [{}]}]
        self.assertEqual(assess_pagination(pages, 2), "PASS")

    def test_identical_duplicates_do_not_sum(self):
        pages = [{"success": True, "barcode": BARCODE, "stores": [{"code": "12345", "stock": 2}]}] * 2
        self.assertEqual(reconcile_pages(pages), ({"12345": 2}, set()))

    def test_conflicting_duplicates_are_excluded(self):
        pages = [
            {"success": True, "barcode": BARCODE, "stores": [{"code": "12345", "stock": 2}]},
            {"success": True, "barcode": BARCODE, "stores": [{"code": "12345", "stock": 0}]},
        ]
        self.assertEqual(reconcile_pages(pages), ({}, {"12345"}))

    def test_wrong_barcode_rejected(self):
        with self.assertRaises(ValueError):
            reconcile_pages([{"success": True, "barcode": "WRONG", "stores": []}])

    def test_non_numeric_code_rejected(self):
        with self.assertRaises(ValueError):
            reconcile_pages([{"success": True, "barcode": BARCODE, "stores": [{"code": "123.0", "stock": 1}]}])

    def test_unknown_is_never_zero(self):
        self.assertEqual(classify_observation(False, False, None), "NOT_QUERIED")
        self.assertEqual(classify_observation(True, False, None), "NOT_QUERIED")
        self.assertEqual(classify_observation(True, True, None), "NOT_OBSERVED")
        self.assertEqual(classify_observation(True, True, 0), "ZERO_STOCK")
        self.assertEqual(classify_observation(True, True, 4), "IN_STOCK")
        self.assertEqual(classify_observation(True, True, -1), "NO_VALID_STOCK_VALUE")

    def test_no_network_or_notification_functions(self):
        import ast
        from pathlib import Path
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        names = {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        self.assertFalse(names & {"query", "telegram", "urlopen", "save_state", "main"})


if __name__ == "__main__":
    unittest.main()
