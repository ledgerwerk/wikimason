from __future__ import annotations

from fnmatch import fnmatchcase
from typing import TYPE_CHECKING

from .config import LoggingConfig

if TYPE_CHECKING:
    from .logs import LogEvent

LEVEL_RANK = {"info": 10, "warning": 20, "error": 30}
NON_CLEAN_STATUSES = {
    "changed",
    "invalid",
    "error",
    "actionable",
    "not_found",
    "ambiguous",
    "skipped",
    "degraded",
}
PROBLEM_STATUSES = {"invalid", "error", "actionable", "not_found", "ambiguous"}


def should_log_event(
    event: LogEvent, config: LoggingConfig, *, force: bool = False
) -> bool:
    if force:
        return True
    if not config.enabled:
        return False
    if LEVEL_RANK.get(event.level, 10) < LEVEL_RANK[config.min_level]:
        return False
    if config.mode == "diagnostic":
        return True
    command = event.command or event.action
    if any(fnmatchcase(command, pattern) for pattern in config.exclude_commands):
        return False
    if config.include_commands:
        return any(fnmatchcase(command, pattern) for pattern in config.include_commands)
    if config.mode == "quiet":
        return (
            event.status in PROBLEM_STATUSES
            or event.level in {"warning", "error"}
            or event.exit_code != 0
        )
    if event.status in PROBLEM_STATUSES or event.exit_code != 0:
        return True
    if event.status in {"changed", "degraded"}:
        return True
    if event.status == "clean" and not config.include_audit_success:
        return False
    return True
