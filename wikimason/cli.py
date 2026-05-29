from __future__ import annotations

import sys

import click
import typer

from .cli_app import app
from .errors import UsageError

# ---------------------------------------------------------------------------
# Legacy alias expansion
# ---------------------------------------------------------------------------

ALIASES: dict[tuple[str, ...], tuple[str, ...]] = {
    ("source-scan",): ("source", "scan"),
    ("source-delta",): ("source", "delta"),
    ("source-coverage",): ("source", "coverage"),
    ("build",): ("index", "build"),
}

_GLOBAL_FLAGS = {"--config", "--env", "--vault"}


def _hoist_global_options(argv: list[str]) -> list[str]:
    """Move --config/--env/--vault from anywhere in argv to the front.

    This preserves backward compatibility with the old CLI which allowed
    global options after the command name (e.g. wikimason doctor --vault PATH).
    """
    globals_part: list[str] = []
    rest: list[str] = []
    i = 0
    while i < len(argv):
        token = argv[i]
        if token in _GLOBAL_FLAGS:
            if i + 1 >= len(argv):
                rest.append(token)
                break
            globals_part.extend([token, argv[i + 1]])
            i += 2
            continue
        rest.append(token)
        i += 1
    return globals_part + rest


def _expand_legacy_alias(argv: list[str]) -> list[str]:
    if not argv:
        return argv
    # Skip global option pairs to find the command
    i = 0
    while i < len(argv) and argv[i] in _GLOBAL_FLAGS:
        i += 2  # skip flag and value
    if i >= len(argv):
        return argv
    head = (argv[i],)
    replacement = ALIASES.get(head)
    if replacement is None:
        return argv
    return [*argv[:i], *replacement, *argv[i + 1 :]]


# ---------------------------------------------------------------------------
# Thin entrypoint
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    raw_args = list(argv if argv is not None else sys.argv[1:])
    raw_args = _expand_legacy_alias(_hoist_global_options(raw_args))

    # Handle --version / -v before Typer, to preserve the old behavior
    # of just printing the version string.
    if raw_args and raw_args[0] in {"-v", "--version", "version"}:
        from . import __version__

        print(f"wikimason {__version__}")
        return 0
    try:
        command = typer.main.get_command(app)
        result = command.main(
            args=raw_args,
            prog_name="wikimason",
            standalone_mode=False,
        )
        if isinstance(result, int):
            return result
        return 0
    except click.exceptions.Exit as exc:
        return int(exc.exit_code)
    except UsageError as exc:
        print(f"error: {exc}")
        return 2
    except Exception as exc:
        # Catch Click/Typer usage errors (different class hierarchies in typer)
        if (
            hasattr(exc, "exit_code")
            and hasattr(exc, "show")
            and hasattr(exc, "format_message")
        ):  # noqa: E501
            exc.show()
            return int(exc.exit_code)
        if hasattr(exc, "exit_code"):
            return int(exc.exit_code)
        raise
    except SystemExit as exc:
        code = exc.code
        if isinstance(code, int):
            return code
        return 0
