from __future__ import annotations

import json
import sys

import click
import typer

from .cli_app import app
from .cli_output import result_payload
from .errors import UsageError

# ---------------------------------------------------------------------------
# Global option handling
# ---------------------------------------------------------------------------

_GLOBAL_FLAGS = {"--config", "--env", "--vault"}


def _hoist_global_options(argv: list[str]) -> list[str]:
    """Move global context options to the front before handing off to Typer.

    This lets CLI examples place `--config`, `--env`, and `--vault` near the
    command that needs context while still using Typer's global-option model.
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


# ---------------------------------------------------------------------------
# Thin entrypoint
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    raw_args = list(argv if argv is not None else sys.argv[1:])
    raw_args = _hoist_global_options(raw_args)

    # Handle --version / -v before Typer, to preserve the old behavior
    # of just printing the version string.
    if raw_args and raw_args[0] in {"-v", "--version", "version"}:
        from . import __version__

        print(f"wikimason {__version__}")
        return 0
    try:
        cli_command = typer.main.get_command(app)
        result = cli_command.main(
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
        if _requested_format(raw_args) == "json":
            command_name = _requested_command(raw_args)
            print(
                json.dumps(
                    result_payload(
                        command=command_name,
                        status="invalid",
                        data={},
                        exit_code=2,
                        errors=[str(exc)],
                    ),
                    sort_keys=True,
                )
            )
        else:
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


def _requested_format(argv: list[str]) -> str:
    for i, token in enumerate(argv):
        if token == "--format" and i + 1 < len(argv):
            return argv[i + 1]
    return "text"


def _requested_command(argv: list[str]) -> str:
    i = 0
    while i < len(argv):
        token = argv[i]
        if token in _GLOBAL_FLAGS:
            i += 2
            continue
        if token.startswith("-"):
            i += 1
            continue
        break
    if i >= len(argv):
        return "cli"
    first = argv[i]
    second = ""
    j = i + 1
    while j < len(argv):
        token = argv[j]
        if token.startswith("-"):
            j += 1
            continue
        second = token
        break
    if not second:
        return first
    return f"{first}.{second}"
