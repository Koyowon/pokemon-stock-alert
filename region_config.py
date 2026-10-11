
"""Shared regional settings for convenience-store monitors."""

import json
from pathlib import Path

CONFIG_FILE = Path(__file__).with_name("region_settings.json")

REGION_NAMES = {
    "namwon": "남원시",
    "asan": "아산시",
    "jeonju": "전주시",
    "jeju": "제주시",
}

DEFAULT_ENABLED = {"namwon", "asan"}


def load_enabled_regions():
    """Read enabled regions, failing safely on invalid settings."""
    if not CONFIG_FILE.exists():
        print("REGION_CONFIG_MISSING: using existing regions")
        return set(DEFAULT_ENABLED)

    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))

        if not isinstance(data, dict):
            raise ValueError("Invalid configuration object")

        if data.get("version") != 1:
            raise ValueError("Unsupported configuration version")

        regions = data.get("regions")

        if not isinstance(regions, list):
            raise ValueError("Invalid regions list")

        enabled = set()
        seen = set()

        for region in regions:
            if not isinstance(region, dict):
                raise ValueError("Invalid region entry")

            region_id = region.get("id")
            status = region.get("enabled")

            if region_id not in REGION_NAMES:
                raise ValueError("Unknown region: " + str(region_id))

            if region_id in seen:
                raise ValueError("Duplicate region: " + region_id)

            if type(status) is not bool:
                raise ValueError("Invalid enabled value")

            seen.add(region_id)

            if status:
                enabled.add(region_id)

        if seen != set(REGION_NAMES):
            raise ValueError("Missing region entries")

        print("ENABLED_REGIONS:", sorted(enabled))
        return enabled

    except (OSError, ValueError, TypeError) as exc:
        print("REGION_CONFIG_ERROR:", str(exc))
        print("Using existing Namwon/Asan settings")
        return set(DEFAULT_ENABLED)


def is_region_enabled(region_id):
    return region_id in load_enabled_regions()
