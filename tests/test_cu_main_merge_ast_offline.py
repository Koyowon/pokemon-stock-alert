"""Exercise the exact main() per-store merge AST, never call main or import monitor."""
import ast
import copy
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "cu_stock_monitor.py"


def load_merge_block():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    matches = [
        n for n in ast.walk(main)
        if isinstance(n, ast.For)
        and isinstance(n.target, ast.Name) and n.target.id == "item"
        and isinstance(n.iter, ast.Name) and n.iter.id == "stores"
    ]
    if len(matches) != 1:
        raise AssertionError("Expected exactly one main() item merge loop")
    block = ast.Module(body=[copy.deepcopy(matches[0])], type_ignores=[])
    ast.fix_missing_locations(block)
    return compile(block, str(SOURCE), "exec")


MERGE_CODE = load_merge_block()


def merge_batches(*batches):
    observed, conflicts = {}, set()
    for stores in batches:
        # Only the extracted AST executes; no query, main, save_state or telegram.
        scope = {"observed": observed, "conflicts": conflicts, "stores": stores,
                 "print": lambda *args, **kwargs: None}
        exec(MERGE_CODE, {"__builtins__": {}}, scope)
    return observed, conflicts


def row(code="12345", stock=2, city="아산", name="A", address="아산 A"):
    return {"code": code, "stock": stock, "city": city, "name": name, "address": address}


class MainMergeOfflineRegression(unittest.TestCase):
    def test_same_code_same_quantity_deduplicated(self):
        observed, conflicts = merge_batches([row()], [row()])
        self.assertEqual(observed, {"12345": row()})
        self.assertEqual(conflicts, set())

    def test_conflicting_quantity_excluded(self):
        observed, conflicts = merge_batches([row(stock=2)], [row(stock=0)])
        self.assertEqual(observed, {})
        self.assertEqual(conflicts, {"12345"})

    def test_conflict_cannot_be_reintroduced(self):
        observed, conflicts = merge_batches([row(stock=2)], [row(stock=0)], [row(stock=2)])
        self.assertEqual(observed, {})
        self.assertEqual(conflicts, {"12345"})

    def test_same_code_different_name_address_same_quantity_first_wins(self):
        first = row(name="점포A", address="주소A")
        second = row(name="점포B", address="주소B")
        observed, conflicts = merge_batches([first], [second])
        self.assertEqual(observed, {"12345": first})
        self.assertEqual(conflicts, set())

    def test_same_code_different_city_conflicts(self):
        observed, conflicts = merge_batches([row(city="아산")], [row(city="전주")])
        self.assertEqual(observed, {})
        self.assertEqual(conflicts, {"12345"})

    def test_unobserved_is_absent_not_zero(self):
        observed, conflicts = merge_batches([], [row(code="22222", stock=0)])
        self.assertNotIn("12345", observed)
        self.assertEqual(observed["22222"]["stock"], 0)
        self.assertEqual(conflicts, set())

    def test_distinct_codes_remain_distinct(self):
        observed, conflicts = merge_batches([row(code="12345"), row(code="22222", stock=0)])
        self.assertEqual(set(observed), {"12345", "22222"})
        self.assertEqual(conflicts, set())


if __name__ == "__main__":
    unittest.main()
