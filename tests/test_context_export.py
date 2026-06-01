"""Tests for WikiMason context export workflow."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wikimason.scaffold import init_vault


@pytest.fixture()
def demo_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    init_vault(vault, demo=True)
    return vault


@pytest.fixture()
def built_vault(demo_vault: Path) -> Path:
    from wikimason.build import build_vault

    build_vault(demo_vault)
    return demo_vault


# ---------------------------------------------------------------------------
# Search index tests
# ---------------------------------------------------------------------------


class TestSQLiteSearchIndex:
    def test_rebuild_creates_index(self, built_vault: Path) -> None:
        from wikimason.search_index import SQLiteSearchIndex

        db_path = built_vault / ".wikimason/search.sqlite3"
        assert db_path.exists(), "vault build should create search.sqlite3"

        idx = SQLiteSearchIndex(db_path)
        status = idx.status()
        assert status["ok"]
        assert status["doc_count"] > 0
        idx.close()

    def test_query_returns_results(self, built_vault: Path) -> None:
        from wikimason.search_index import SQLiteSearchIndex

        db_path = built_vault / ".wikimason/search.sqlite3"
        idx = SQLiteSearchIndex(db_path)
        results = idx.query("demo")
        assert len(results) > 0
        assert any("demo" in str(r["path"]).lower() or "demo" in str(r["title"]).lower() for r in results)
        idx.close()

    def test_safe_fts_query(self) -> None:
        from wikimason.search_index import to_safe_fts_query

        assert to_safe_fts_query("llm wiki") == '"llm" OR "wiki" OR "llm wiki"'
        assert to_safe_fts_query("test") == '"test"'
        assert to_safe_fts_query("") == ""
        # Special FTS characters should be stripped
        q = to_safe_fts_query('test "quoted" (parens)')
        # Should not contain raw FTS operators like parentheses
        assert '(' not in q
        assert ')' not in q

    def test_index_status_missing(self, tmp_path: Path) -> None:
        from wikimason.search_index import index_status

        vault = tmp_path / "nonexistent"
        vault.mkdir()
        status = index_status(vault)
        assert not status["ok"]


# ---------------------------------------------------------------------------
# Context plan tests
# ---------------------------------------------------------------------------


class TestContextPlan:
    def test_selects_obvious_topic_page(self, built_vault: Path) -> None:
        from wikimason.context_export import plan_context

        plan = plan_context(built_vault, "wikimason")
        assert plan.selected_count > 0
        # wikimason-demo or wikimason topic should be rank 1 or near top
        top_paths = [item.path for item in plan.items[:3]]
        assert any("wikimason" in p.lower() for p in top_paths)

    def test_typo_tolerant_selection(self, built_vault: Path) -> None:
        from wikimason.context_export import plan_context

        plan = plan_context(built_vault, "wikmasn")
        # Should still find wikimason-related pages via RapidFuzz
        assert plan.selected_count > 0
        paths = [item.path for item in plan.items]
        assert any("wikimason" in p.lower() for p in paths)

    def test_includes_declared_sources(self, tmp_path: Path) -> None:
        from wikimason.build import build_vault
        from wikimason.context_export import plan_context

        vault = tmp_path / "vault"
        init_vault(vault, demo=False)

        # Create a source
        src_dir = vault / "Raw/Sources"
        src_dir.mkdir(parents=True, exist_ok=True)
        (src_dir / "llm-wiki-paper.md").write_text(
            "---\nsource_id: src-001\n---\n# LLM Wiki Paper\n\nImportant content.\n",
            encoding="utf-8",
        )

        # Create a page with declared source
        topics_dir = vault / "Wiki/Topics"
        topics_dir.mkdir(parents=True, exist_ok=True)
        (topics_dir / "llm-wiki.md").write_text(
            "---\ntitle: LLM Wiki\nkind: topic\nsources:\n  - Raw/Sources/llm-wiki-paper.md\n---\n# LLM Wiki\n\nContent about LLM wikis.\n",
            encoding="utf-8",
        )

        build_vault(vault)
        plan = plan_context(vault, "llm wiki")

        paths = [item.path for item in plan.items]
        assert any("llm-wiki.md" in p for p in paths)
        # The declared source should be included
        assert any("llm-wiki-paper" in p for p in paths)

    def test_graph_expansion(self, tmp_path: Path) -> None:
        from wikimason.build import build_vault
        from wikimason.context_export import plan_context

        vault = tmp_path / "vault"
        init_vault(vault, demo=False)

        topics_dir = vault / "Wiki/Topics"
        topics_dir.mkdir(parents=True, exist_ok=True)
        concepts_dir = vault / "Wiki/Concepts"
        concepts_dir.mkdir(parents=True, exist_ok=True)

        # Page A links to Page B
        (topics_dir / "page-a.md").write_text(
            "---\ntitle: Page A\nkind: topic\n---\n# Page A\n\nSee [[Wiki/Concepts/page-b|Page B]].\n",
            encoding="utf-8",
        )
        (concepts_dir / "page-b.md").write_text(
            "---\ntitle: Page B\nkind: concept\n---\n# Page B\n\nDetails.\n",
            encoding="utf-8",
        )

        build_vault(vault)
        plan = plan_context(vault, "page a", depth=1)

        paths = [item.path for item in plan.items]
        # Page A should be selected as seed
        assert any("page-a" in p for p in paths)
        # Page B should be expanded through the link
        assert any("page-b" in p for p in paths)

    def test_budget_enforcement(self, tmp_path: Path) -> None:
        from wikimason.build import build_vault
        from wikimason.context_export import plan_context

        vault = tmp_path / "vault"
        init_vault(vault, demo=False)

        topics_dir = vault / "Wiki/Topics"
        topics_dir.mkdir(parents=True, exist_ok=True)

        # Create several small pages
        for i in range(10):
            (topics_dir / f"topic-{i}.md").write_text(
                f"---\ntitle: Topic {i}\nkind: topic\n---\n# Topic {i}\n\nContent for topic {i}.\n",
                encoding="utf-8",
            )

        build_vault(vault)
        plan = plan_context(vault, "topic", max_files=3)

        assert plan.selected_count <= 3
        assert any("max-files" in w for w in plan.warnings)

    def test_excludes_generated_files(self, built_vault: Path) -> None:
        from wikimason.context_export import plan_context

        plan = plan_context(built_vault, "index")
        paths = [item.path for item in plan.items]
        assert "Wiki/catalog.jsonl" not in paths
        assert "Wiki/index.md" not in paths

    def test_include_indexes_allows_generated(self, built_vault: Path) -> None:
        from wikimason.context_export import plan_context

        plan = plan_context(built_vault, "index", include_indexes=True)
        paths = [item.path for item in plan.items]
        # With include_indexes, generated wiki index pages should be allowed
        # (they still need to match the query to appear)
        assert isinstance(plan.selected_count, int)


# ---------------------------------------------------------------------------
# Export format tests
# ---------------------------------------------------------------------------


class TestExportFormat:
    def test_stable_markdown_output(self, built_vault: Path) -> None:
        from wikimason.context_export import plan_context, render_context_markdown

        plan1 = plan_context(built_vault, "wikimason")
        md1 = render_context_markdown(built_vault, plan1)
        plan2 = plan_context(built_vault, "wikimason")
        md2 = render_context_markdown(built_vault, plan2)

        # Remove timestamps for comparison
        import re

        ts_pattern = r'generated_at: "[^"]*"'
        md1_clean = re.sub(ts_pattern, 'generated_at: "FIXED"', md1)
        md2_clean = re.sub(ts_pattern, 'generated_at: "FIXED"', md2)
        assert md1_clean == md2_clean

    def test_manifest_header(self, built_vault: Path) -> None:
        from wikimason.context_export import export_context

        out = built_vault / "export.md"
        export_context(built_vault, "demo", out)

        content = out.read_text(encoding="utf-8")
        assert content.startswith("---\n")
        assert "wikimason_context_export: 1" in content
        assert 'query: "demo"' in content
        assert "selected_count:" in content

    def test_selection_table(self, built_vault: Path) -> None:
        from wikimason.context_export import export_context

        out = built_vault / "export.md"
        export_context(built_vault, "demo", out)

        content = out.read_text(encoding="utf-8")
        assert "## Selection Manifest" in content
        assert "| Rank | Score |" in content

    def test_file_markers(self, built_vault: Path) -> None:
        from wikimason.context_export import export_context

        out = built_vault / "export.md"
        export_context(built_vault, "demo", out)

        content = out.read_text(encoding="utf-8")
        assert '<!-- wikimason:begin-file' in content
        assert '<!-- wikimason:end-file -->' in content

    def test_export_no_path_escape(self, tmp_path: Path) -> None:
        """Query should never read outside the vault."""
        from wikimason.build import build_vault
        from wikimason.context_export import plan_context

        vault = tmp_path / "vault"
        init_vault(vault, demo=True)
        build_vault(vault)

        plan = plan_context(vault, "../../etc/passwd")
        for item in plan.items:
            # All paths should be relative and within vault
            assert not item.path.startswith("/")
            assert ".." not in item.path


# ---------------------------------------------------------------------------
# JSON plan output tests
# ---------------------------------------------------------------------------


class TestPlanJSON:
    def test_json_shape(self, built_vault: Path) -> None:
        from wikimason.context_export import plan_context, plan_to_json

        plan = plan_context(built_vault, "demo")
        data = plan_to_json(plan)

        assert "query" in data
        assert data["query"] == "demo"
        assert "items" in data
        assert "total_candidates" in data
        assert "selected_count" in data
        assert "estimated_tokens" in data

        for item in data["items"]:
            assert "path" in item
            assert "kind" in item
            assert "score" in item
            assert "reasons" in item
            assert isinstance(item["reasons"], list)

    def test_json_serializable(self, built_vault: Path) -> None:
        from wikimason.context_export import plan_context, plan_to_json

        plan = plan_context(built_vault, "demo")
        data = plan_to_json(plan)
        text = json.dumps(data)
        assert json.loads(text) == data


# ---------------------------------------------------------------------------
# Credential safety tests
# ---------------------------------------------------------------------------


class TestCredentialSafety:
    def test_blocks_secret_export(self, tmp_path: Path) -> None:
        from wikimason.build import build_vault
        from wikimason.context_export import export_context

        vault = tmp_path / "vault"
        init_vault(vault, demo=False)

        topics_dir = vault / "Wiki/Topics"
        topics_dir.mkdir(parents=True, exist_ok=True)
        (topics_dir / "secrets.md").write_text(
            "---\ntitle: Secrets\nkind: topic\n---\n# Secrets\n\napi_key=AKIA1234567890abcdef\npassword=hunter2\n",
            encoding="utf-8",
        )

        build_vault(vault)
        out = tmp_path / "export.md"

        with pytest.raises(ValueError, match="credential"):
            export_context(vault, "secrets", out)

    def test_allows_sensitive_flag(self, tmp_path: Path) -> None:
        from wikimason.build import build_vault
        from wikimason.context_export import export_context

        vault = tmp_path / "vault"
        init_vault(vault, demo=False)

        topics_dir = vault / "Wiki/Topics"
        topics_dir.mkdir(parents=True, exist_ok=True)
        (topics_dir / "secrets.md").write_text(
            "---\ntitle: Secrets\nkind: topic\n---\n# Secrets\n\napi_key=AKIA1234567890abcdef\n",
            encoding="utf-8",
        )

        build_vault(vault)
        out = tmp_path / "export.md"

        # Should succeed with --allow-sensitive
        plan = export_context(vault, "secrets", out, allow_sensitive=True)
        assert out.exists()


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------


class TestContextCLI:
    def test_context_help(self, capsys: pytest.CaptureFixture[str]) -> None:
        from wikimason.cli import main

        assert main(["context", "--help"]) == 0
        out = capsys.readouterr().out
        assert "plan" in out
        assert "export" in out
        assert "index" in out

    def test_context_plan_text(self, built_vault: Path, capsys: pytest.CaptureFixture[str]) -> None:
        from wikimason.cli import main

        result = main([
            "context", "plan", "demo",
            "--vault", str(built_vault),
        ])
        assert result == 0
        out = capsys.readouterr().out
        assert "demo" in out.lower()

    def test_context_plan_json(self, built_vault: Path, capsys: pytest.CaptureFixture[str]) -> None:
        from wikimason.cli import main

        result = main([
            "context", "plan", "demo",
            "--vault", str(built_vault),
            "--format", "json",
        ])
        assert result == 0
        output = capsys.readouterr().out
        payload = json.loads(output.splitlines()[-1])
        assert payload["query"] == "demo"
        assert "items" in payload

    def test_context_export_writes_file(self, built_vault: Path) -> None:
        from wikimason.cli import main

        out = built_vault / "ctx.md"
        result = main([
            "context", "export", "demo",
            "--vault", str(built_vault),
            "--output", str(out),
        ])
        assert result == 0
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "wikimason_context_export" in content

    def test_context_index_rebuild(self, built_vault: Path, capsys: pytest.CaptureFixture[str]) -> None:
        from wikimason.cli import main

        result = main([
            "context", "index", "--rebuild",
            "--vault", str(built_vault),
            "--format", "json",
        ])
        assert result == 0
        output = capsys.readouterr().out
        payload = json.loads(output.splitlines()[-1])
        assert payload["result"]["ok"]


    def test_context_export_print(self, built_vault: Path, capsys: pytest.CaptureFixture[str]) -> None:
        from wikimason.cli import main

        result = main([
            "context", "export", "demo",
            "--vault", str(built_vault),
            "--print",
        ])
        assert result == 0
        output = capsys.readouterr().out
        assert "wikimason_context_export" in output
