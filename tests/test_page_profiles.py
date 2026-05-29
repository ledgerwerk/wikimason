from __future__ import annotations

from pathlib import Path

from wikimason.config import default_config, write_config_file
from wikimason.link_format import format_link
from wikimason.page_profiles import (
    logical_ref_to_relpath,
    relpath_to_logical_ref,
    render_page_text,
    split_page_text,
)
from wikimason.paths import build_link_targets, compiled_md_files


def test_logseq_page_profile_maps_logical_refs_to_flat_pages(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    config = default_config("logseq", vault)

    assert (
        logical_ref_to_relpath("Wiki/Topics/wikimason", config=config)
        == "pages/Wiki___Topics___wikimason.md"
    )
    assert (
        relpath_to_logical_ref("pages/Wiki___Topics___wikimason.md", config=config)
        == "Wiki/Topics/wikimason"
    )


def test_logseq_page_round_trip_preserves_properties_and_markdown_body(
    tmp_path: Path,
) -> None:
    config = default_config("logseq", tmp_path / "vault")
    body = """## Deployment Pipeline

Ship the documented steps.

### Release Checklist

1. Run tests
2. Publish package

- Capture release notes

```python
print("ok")
```

| Step | Owner |
| --- | --- |
| Publish | Team |

See [[Wiki/Topics/wikimason|WikiMason]].
"""
    text = render_page_text(
        {
            "tags": ["concept", "build"],
            "status": "active",
            "sources": ["Raw/Sources/demo.md"],
            "aliases": ["Deployment Pipeline"],
        },
        body,
        config=config,
    )

    assert "- tags:: concept, build" in text
    assert "- ## Deployment Pipeline" in text
    assert "  - Ship the documented steps." in text
    assert "    - 1. Run tests" in text
    assert "    - ```python" in text
    assert '      - print("ok")' in text
    assert "    - | Step | Owner |" in text

    data, parsed_body = split_page_text(text, config=config)

    assert data == {
        "tags": ["concept", "build"],
        "status": "active",
        "sources": ["Raw/Sources/demo.md"],
        "aliases": ["Deployment Pipeline"],
    }
    assert parsed_body == body


def test_logseq_pages_are_discoverable_by_compiled_and_link_target_helpers(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    config = default_config("logseq", vault)
    write_config_file(vault / "wikimason.toml", config, root_value=".")
    pages = vault / "pages"
    pages.mkdir(parents=True)
    page = pages / "Wiki___Topics___wikimason.md"
    page.write_text(
        render_page_text(
            {
                "tags": ["topic"],
                "topics": [],
                "status": "active",
                "created": "2026-05-29",
                "updated": "2026-05-29",
                "sources": [],
                "source_count": 0,
                "aliases": [],
            },
            "# WikiMason\n",
            config=config,
        ),
        encoding="utf-8",
    )

    assert list(compiled_md_files(vault)) == [page]

    targets = build_link_targets(vault)
    assert "Wiki/Topics/wikimason" in targets
    assert "Wiki/Topics/wikimason.md" in targets
    assert (
        format_link(
            config.links, "pages/Wiki___Topics___wikimason.md", label="WikiMason"
        )
        == "[[Wiki/Topics/wikimason|WikiMason]]"
    )
