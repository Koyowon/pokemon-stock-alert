"""Pure text formatter for an Asan CU stock snapshot; no side effects."""

VALID_STATUSES = frozenset(("IN_STOCK", "ZERO_STOCK", "NOT_OBSERVED", "NOT_QUERIED", "NO_VALID_STOCK_VALUE"))


def format_asan_stock_message(snapshot):
    """Format all registry rows without conflating unknown stock with zero."""
    rows = snapshot["candidates"]
    if snapshot["candidate_count"] != len(rows) or len({r["registry_id"] for r in rows}) != len(rows):
        raise ValueError("Invalid snapshot candidate count or duplicate registry IDs")
    lines = ["📋 아산 CU 포켓몬 30주년 카드 재고 현황", f"바코드: {snapshot['barcode']}", f"등록 점포: {len(rows)}개", "※ 조회된 점포의 수량만 표시하며 미확인은 품절이 아닙니다.", ""]
    groups = {"IN_STOCK": [], "ZERO_STOCK": [], "UNKNOWN": []}
    for row in rows:
        status, stock = row["status"], row["stock"]
        if status not in VALID_STATUSES:
            raise ValueError("Unknown snapshot status")
        if status == "IN_STOCK":
            if type(stock) is not int or stock <= 0:
                raise ValueError("IN_STOCK requires positive integer stock")
            groups["IN_STOCK"].append(f"• {row['name']} [{row['registry_id']}] — {stock}개")
        elif status == "ZERO_STOCK":
            if type(stock) is not int or stock != 0:
                raise ValueError("ZERO_STOCK requires zero stock")
            groups["ZERO_STOCK"].append(f"• {row['name']} [{row['registry_id']}] — 0개")
        else:
            groups["UNKNOWN"].append(f"• {row['name']} [{row['registry_id']}] — 미확인 ({status})")
    for heading, key in (("🟢 재고 있음", "IN_STOCK"), ("⚪ 재고 0개", "ZERO_STOCK"), ("❔ 재고 미확인", "UNKNOWN")):
        lines.append(f"{heading}: {len(groups[key])}개 점포")
        lines.extend(groups[key] or ["• 해당 없음"])
        lines.append("")
    return "\n".join(lines).rstrip()
