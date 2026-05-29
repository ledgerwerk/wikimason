"""Review queue domain module.

Reads and writes a JSONL review queue at Schema/review.jsonl.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

REVIEW_QUEUE_FILE = "Schema/review.jsonl"


@dataclass
class ReviewItem:
    review_id: str
    created_at: str
    kind: str  # create_page|merge_conflict|research_gap|source_conflict|unsafe_secret
    source_id: str
    title: str
    detail: str
    suggested_actions: list[str]
    status: str  # open|accepted|skipped|done

    @classmethod
    def new(
        cls,
        *,
        kind: str,
        source_id: str = "",
        title: str = "",
        detail: str = "",
        suggested_actions: list[str] | None = None,
    ) -> ReviewItem:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        import secrets

        unique = secrets.token_hex(3)
        review_id = f"rev_{datetime.now(timezone.utc).strftime('%Y%m%d')}_{unique}"
        return cls(
            review_id=review_id,
            created_at=now,
            kind=kind,
            source_id=source_id,
            title=title,
            detail=detail,
            suggested_actions=suggested_actions or [],
            status="open",
        )


def review_queue_path(vault: Path) -> Path:
    return vault / REVIEW_QUEUE_FILE


def load_review_queue(vault: Path) -> list[ReviewItem]:
    """Read all review items from the JSONL queue."""
    path = review_queue_path(vault)
    if not path.exists():
        return []
    items: list[ReviewItem] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            items.append(ReviewItem(**data))
        except (json.JSONDecodeError, TypeError):
            continue
    return items


def save_review_queue(vault: Path, items: list[ReviewItem]) -> None:
    """Write the full review queue to JSONL."""
    path = review_queue_path(vault)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(asdict(item), sort_keys=True) for item in items]
    path.write_text("\n".join(lines) + "\n" if lines else "", encoding="utf-8")


def add_review_item(vault: Path, item: ReviewItem) -> None:
    """Append a single review item to the queue."""
    items = load_review_queue(vault)
    items.append(item)
    save_review_queue(vault, items)


def find_review_item(vault: Path, review_id: str) -> ReviewItem | None:
    """Find a review item by its review_id."""
    for item in load_review_queue(vault):
        if item.review_id == review_id:
            return item
    return None


def resolve_review_item(vault: Path, review_id: str, status: str) -> ReviewItem | None:
    """Set the status of a review item and persist."""
    items = load_review_queue(vault)
    for i, item in enumerate(items):
        if item.review_id == review_id:
            items[i] = ReviewItem(
                review_id=item.review_id,
                created_at=item.created_at,
                kind=item.kind,
                source_id=item.source_id,
                title=item.title,
                detail=item.detail,
                suggested_actions=item.suggested_actions,
                status=status,
            )
            save_review_queue(vault, items)
            return items[i]
    return None


def seed_review_queue(vault: Path) -> Path:
    """Create an empty review queue file if it doesn't exist."""
    path = review_queue_path(vault)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
    return path
