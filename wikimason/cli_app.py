"""WikiMason CLI app composition root.

Thin builder that creates the Typer app and registers modular command groups.
All command logic lives in ``cli_groups/`` and ``cli_helpers.py``.
"""

from __future__ import annotations

from pathlib import Path

import typer

from .cli_state import CliState

# ---------------------------------------------------------------------------
# Root app
# ---------------------------------------------------------------------------

try:
    from .cli_suggestions import FuzzyCommandGroup

    app = typer.Typer(
        name="wikimason",
        help="Filesystem-backed CLI toolkit for building and maintaining an LLM wiki.",
        no_args_is_help=True,
        add_completion=False,
        cls=FuzzyCommandGroup,
    )
except ImportError:
    app = typer.Typer(
        name="wikimason",
        help="Filesystem-backed CLI toolkit for building and maintaining an LLM wiki.",
        no_args_is_help=True,
        add_completion=False,
    )


@app.callback()
def main_callback(
    ctx: typer.Context,
    config: str | None = typer.Option(
        None, "--config", help="Use an explicit WikiMason TOML config file."
    ),
    env: str | None = typer.Option(None, "--env", help="Select a named env config."),
    vault: str | None = typer.Option(
        None, "--vault", help="Wiki root override."
    ),
) -> None:
    """Global callback: initialises CliState on the context."""
    ctx.ensure_object(dict)
    ctx.obj = CliState(
        env=env,
        config_path=Path(config) if config else None,
        vault=Path(vault) if vault else None,
    )


# ---------------------------------------------------------------------------
# Register modular command groups
# ---------------------------------------------------------------------------

from .cli_groups.agents import register_agents
from .cli_groups.catalog import register_catalog
from .cli_groups.config import register_config
from .cli_groups.daily import register_daily
from .cli_groups.file import register_file
from .cli_groups.folder import register_folder
from .cli_groups.index import register_index
from .cli_groups.ingest import register_ingest
from .cli_groups.links import register_links
from .cli_groups.migrate import register_migrate
from .cli_groups.note import register_note
from .cli_groups.page import register_page
from .cli_groups.property import register_property
from .cli_groups.review import register_review
from .cli_groups.root import register_root
from .cli_groups.skill import register_skill
from .cli_groups.source import register_source
from .cli_groups.tag import register_tag
from .cli_groups.task import register_task
from .cli_groups.template import register_template
from .cli_groups.text import register_text
from .cli_groups.vault import register_vault

register_root(app)
register_agents(app)
register_catalog(app)
register_config(app)
register_daily(app)
register_file(app)
register_folder(app)
register_index(app)
register_ingest(app)
register_links(app)
register_migrate(app)
register_note(app)
register_page(app)
register_property(app)
register_review(app)
register_skill(app)
register_source(app)
register_tag(app)
register_task(app)
register_template(app)
register_text(app)
register_vault(app)
