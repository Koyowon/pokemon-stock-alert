"""Pure Telegram-safe chunking and preview; no network or side effects."""
from asan_stock_message import format_asan_stock_message

TELEGRAM_TEXT_LIMIT = 4096


def split_telegram_text(message, *, limit=TELEGRAM_TEXT_LIMIT):
    """Split on line boundaries, preserving text/order and adding page labels."""
    if not isinstance(message, str) or not message:
        raise ValueError("Message must be nonempty text")
    if type(limit) is not int or not 32 <= limit <= TELEGRAM_TEXT_LIMIT:
        raise ValueError("Invalid Telegram message limit")
    # Reserve a generous, fixed header budget to avoid a circular page count.
    budget = limit - 24
    lines = message.split("\n")
    if any(len(line) > budget for line in lines):
        raise ValueError("A line exceeds the safe message chunk size")
    pages, current = [], []
    for line in lines:
        proposal = "\n".join(current + [line])
        if current and len(proposal) > budget:
            pages.append("\n".join(current))
            current = [line]
        else:
            current.append(line)
    pages.append("\n".join(current))
    if len(pages) == 1 and len(message) <= limit:
        return [message]
    total = len(pages)
    result = [f"[{i}/{total}]\n{page}" for i, page in enumerate(pages, 1)]
    if any(len(page) > limit for page in result):
        raise ValueError("Page header exceeds reserved capacity")
    return result


def preview_asan_stock_messages(snapshot, *, limit=TELEGRAM_TEXT_LIMIT):
    """Produce the exact outgoing text pages for inspection, without sending."""
    return split_telegram_text(format_asan_stock_message(snapshot), limit=limit)
