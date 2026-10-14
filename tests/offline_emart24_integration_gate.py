"""Pure offline integration gate for Jeju support. Does not import or run monitor.py."""
import ast
from pathlib import Path

TARGET = "8800286275732"


def inspect_monitor(source):
    tree = ast.parse(source)
    assignments = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ("PRODUCTS", "REGIONS", "REGION_IDS"):
                    assignments[target.id] = ast.literal_eval(node.value)
    products = assignments.get("PRODUCTS", {})
    regions = assignments.get("REGIONS", {})
    ids = assignments.get("REGION_IDS", {})
    return {
        "only_30th_product": len(products) == 1 and list(products.values()) == [TARGET],
        "jeju_region_declared": regions.get("제주") == "제주시" and ids.get("제주") == "jeju",
        "jeju_offline_integration_ready": False,  # Needs verified seed and code path, not just region flags.
        "has_decrease_branch": "qty < old" in source,
        "has_sold_out_branch": "qty == 0" in source,
        "has_unknown_skip": "if qty is None:" in source and "continue" in source,
        "has_bounded_batch_failures": "consecutive_failures >= 3" in source,
    }


def validate_before_merge(monitor_path, seed_readiness):
    result = inspect_monitor(Path(monitor_path).read_text(encoding="utf-8"))
    result["seed_ready"] = seed_readiness.get("ready") is True
    result["can_activate_jeju"] = all([
        result["only_30th_product"], result["jeju_region_declared"],
        result["jeju_offline_integration_ready"], result["seed_ready"],
        result["has_decrease_branch"], result["has_sold_out_branch"],
        result["has_unknown_skip"],
    ])
    return result
