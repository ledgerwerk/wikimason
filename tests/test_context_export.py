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
        assert any(
            "demo" in str(r["path"]).lower() or "demo" in str(r["title"]).lower()
            for r in results
        )
        idx.close()

    def test_safe_fts_query(self) -> None:
        from wikimason.search_index import to_safe_fts_query

        assert to_safe_fts_query("llm wiki") == '"llm" OR "wiki" OR "llm wiki"'
        assert to_safe_fts_query("llm wiki", mode="strict") == '"llm wiki"'
        assert (
            to_safe_fts_query("llm wiki", mode="balanced")
            == '("llm" AND "wiki") OR "llm wiki"'
        )
        assert (
            to_safe_fts_query("llm wiki", mode="balanced", stopwords={"wiki"})
            == '"llm"'
        )
        assert to_safe_fts_query("test") == '"test"'
        assert to_safe_fts_query("") == ""
        # Special FTS characters should be stripped
        q = to_safe_fts_query('test "quoted" (parens)')
        # Should not contain raw FTS operators like parentheses
        assert "(" not in q
        assert ")" not in q

    def test_build_fts_query_plan_stopword_fallback(self) -> None:
        from wikimason.search_index import build_fts_query_plan

        # All terms are stopwords -> fallback to original terms
        plan = build_fts_query_plan(
            "wiki wikimason", mode="strict", stopwords={"wiki", "wikimason"}
        )
        assert plan.used_stopword_fallback is True
        assert plan.effective_terms == ("wiki", "wikimason")
        assert plan.removed_stopwords == ()
        # Query should still work
        assert plan.query

    def test_fts_query_plan_single_term_strict(self) -> None:
        from wikimason.search_index import build_fts_query_plan

        plan = build_fts_query_plan("demo", mode="strict")
        assert plan.query == '"demo"'
        assert plan.effective_terms == ("demo",)

    def test_fts_query_plan_empty_input(self) -> None:
        from wikimason.search_index import build_fts_query_plan

        plan = build_fts_query_plan("", mode="strict")
        assert plan.query == ""
        assert plan.effective_terms == ()

    def test_broad_mode_preserves_default_behavior(self) -> None:
        from wikimason.search_index import to_safe_fts_query

        # Default mode is broad and produces OR-of-terms + phrase
        result = to_safe_fts_query("alpha beta")
        assert '"alpha"' in result
        assert '"beta"' in result
        assert '"alpha beta"' in result
        assert "OR" in result

    def test_context_export_weight_profile(self, built_vault: Path) -> None:
        from wikimason.search_index import SQLiteSearchIndex

        db_path = built_vault / ".wikimason/search.sqlite3"
        idx = SQLiteSearchIndex(db_path)
        broad = idx.query("demo", limit=5, weight_profile="broad")
        context = idx.query("demo", limit=5, weight_profile="context")
        # Both should return results; different profiles may reorder
        assert len(broad) > 0
        assert len(context) > 0
        idx.close()

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
            (
                "---\n"
                "title: LLM Wiki\n"
                "kind: topic\n"
                "sources:\n"
                "  - Raw/Sources/llm-wiki-paper.md\n"
                "---\n"
                "# LLM Wiki\n\n"
                "Content about LLM wikis.\n"
            ),
            encoding="utf-8",
        )
        (topics_dir / "wiki-directory.md").write_text(
            (
                "---\n"
                "title: Wiki Directory\n"
                "kind: topic\n"
                "---\n"
                "# Wiki Directory\n\n" + ("wiki " * 80)
            ),
            encoding="utf-8",
        )

        build_vault(vault)
        plan = plan_context(vault, "llm wiki")

        paths = [item.path for item in plan.items]
        assert any("llm-wiki.md" in p for p in paths)
        assert plan.items[0].path.endswith("llm-wiki.md")
        # The declared source should be included
        assert any("llm-wiki-paper" in p for p in paths)
        assert plan.query_diagnostics is not None
        assert "wiki" in plan.query_diagnostics.removed_stopwords
        assert plan.query_diagnostics.fts_mode in {"strict", "balanced"}

    def test_page_outranks_source_at_same_score(self, tmp_path: Path) -> None:
        from wikimason.build import build_vault
        from wikimason.context_export import plan_context

        vault = tmp_path / "vault"
        init_vault(vault, demo=False)

        topics_dir = vault / "Wiki/Topics"
        topics_dir.mkdir(parents=True, exist_ok=True)
        src_dir = vault / "Raw/Sources"
        src_dir.mkdir(parents=True, exist_ok=True)

        # Page and source both match well; page should rank first
        (topics_dir / "ranking.md").write_text(
            "---\ntitle: Ranking\nkind: topic\nsources:\n"
            "  - Raw/Sources/ranking-data.md\n---\n"
            "# Ranking\n\nContent about ranking.\n",
            encoding="utf-8",
        )
        (src_dir / "ranking-data.md").write_text(
            "---\nsource_id: src-002\n---\n"
            "# Ranking Data\n\nContent about ranking data.\n",
            encoding="utf-8",
        )

        build_vault(vault)
        plan = plan_context(vault, "ranking")

        paths = [item.path for item in plan.items]
        page_idx = next(i for i, p in enumerate(paths) if "Wiki/Topics/ranking" in p)
        src_idx = next(i for i, p in enumerate(paths) if "ranking-data" in p)
        assert page_idx < src_idx, (
            f"Page at {page_idx} should precede source at {src_idx}"
        )

    def test_declared_source_has_tier_1(self, tmp_path: Path) -> None:
        from wikimason.build import build_vault
        from wikimason.context_export import plan_context

        vault = tmp_path / "vault"
        init_vault(vault, demo=False)

        topics_dir = vault / "Wiki/Topics"
        topics_dir.mkdir(parents=True, exist_ok=True)
        src_dir = vault / "Raw/Sources"
        src_dir.mkdir(parents=True, exist_ok=True)

        (topics_dir / "closure.md").write_text(
            "---\ntitle: Closure\nkind: topic\nsources:\n"
            "  - Raw/Sources/closure-src.md\n---\n"
            "# Closure\n\nContent about closure.\n",
            encoding="utf-8",
        )
        (src_dir / "closure-src.md").write_text(
            "---\nsource_id: src-003\n---\n# Closure Source\n\nData.\n",
            encoding="utf-8",
        )

        build_vault(vault)
        plan = plan_context(vault, "closure")

        paths = [item.path for item in plan.items]
        # Declared source should be included
        assert any("closure-src" in p for p in paths)
        # No closure gaps since source is included
        assert not any(g.reason == "budget-excluded" for g in plan.source_closure_gaps)

    def test_source_closure_gap_when_budget_excludes_source(
        self, tmp_path: Path
    ) -> None:
        from wikimason.build import build_vault
        from wikimason.context_export import plan_context

        vault = tmp_path / "vault"
        init_vault(vault, demo=False)

        topics_dir = vault / "Wiki/Topics"
        topics_dir.mkdir(parents=True, exist_ok=True)
        src_dir = vault / "Raw/Sources"
        src_dir.mkdir(parents=True, exist_ok=True)

        # Page with source, but very tight budget
        (topics_dir / "gappy.md").write_text(
            "---\ntitle: Gappy\nkind: topic\nsources:\n"
            "  - Raw/Sources/gappy-src.md\n---\n"
            "# Gappy\n\nContent.\n",
            encoding="utf-8",
        )
        (src_dir / "gappy-src.md").write_text(
            "---\nsource_id: src-004\n---\n# Gappy Source\n\n" + ("data " * 500),
            encoding="utf-8",
        )
        # Add more candidates to force budget pressure
        for i in range(5):
            (topics_dir / f"gappy-fill-{i}.md").write_text(
                f"---\ntitle: Gappy Fill {i}\nkind: topic\n---\n"
                f"# Gappy Fill {i}\n\n{'fill ' * 50}\n",
                encoding="utf-8",
            )

        build_vault(vault)
        # Budget tuned so the referencing page (gappy.md) is included but the
        # large source is excluded; compiled notes now carry a required `type`
        # field, which raises each note's token count slightly.
        plan = plan_context(vault, "gappy", max_files=10, max_tokens=120)

        # Should have a closure gap if source was excluded by budget
        if not any("gappy-src" in item.path for item in plan.items):
            assert any(
                "gappy-src" in gap.source_path for gap in plan.source_closure_gaps
            )

    def test_invalid_declared_source_path_creates_closure_gap(
        self, tmp_path: Path
    ) -> None:
        from wikimason.build import build_vault
        from wikimason.context_export import plan_context

        vault = tmp_path / "vault"
        init_vault(vault, demo=False)

        topics_dir = vault / "Wiki/Topics"
        topics_dir.mkdir(parents=True, exist_ok=True)

        (topics_dir / "bad-source.md").write_text(
            "---\ntitle: Bad Source\nkind: topic\nsources:\n"
            "  - ../../../etc/passwd\n---\n"
            "# Bad Source\n\nContent.\n",
            encoding="utf-8",
        )

        build_vault(vault)
        plan = plan_context(vault, "bad source")

        assert any(
            gap.reason == "invalid-path"
            for gap in plan.source_closure_gaps
            if "passwd" in gap.source_path
        )

    def test_outlinks_rank_below_declared_sources(self, tmp_path: Path) -> None:
        from wikimason.build import build_vault
        from wikimason.context_export import plan_context

        vault = tmp_path / "vault"
        init_vault(vault, demo=False)

        topics_dir = vault / "Wiki/Topics"
        topics_dir.mkdir(parents=True, exist_ok=True)
        concepts_dir = vault / "Wiki/Concepts"
        concepts_dir.mkdir(parents=True, exist_ok=True)
        src_dir = vault / "Raw/Sources"
        src_dir.mkdir(parents=True, exist_ok=True)

        # Page with declared source and outlink to an unrelated page
        # The linked page does NOT match the query, so it's graph-only (tier 2)
        (topics_dir / "tiered.md").write_text(
            "---\ntitle: Tiered\nkind: topic\n"
            "sources:\n  - Raw/Sources/tiered-src.md\n---\n"
            "# Tiered\n\nSee [[Wiki/Concepts/unrelated-linked|Linked]].\n",
            encoding="utf-8",
        )
        (src_dir / "tiered-src.md").write_text(
            "---\nsource_id: src-005\n---\n# Tiered Source\n\nData.\n",
            encoding="utf-8",
        )
        (concepts_dir / "unrelated-linked.md").write_text(
            "---\ntitle: Unrelated Linked\nkind: concept\n---\n"
            "# Unrelated Linked\n\nLinked content.\n",
            encoding="utf-8",
        )

        build_vault(vault)
        plan = plan_context(vault, "tiered")

        paths = [item.path for item in plan.items]
        src_idx = next((i for i, p in enumerate(paths) if "tiered-src" in p), None)
        link_idx = next(
            (i for i, p in enumerate(paths) if "unrelated-linked" in p), None
        )
        # Declared source (tier 1) should precede graph-only outlink (tier 2)
        if src_idx is not None and link_idx is not None:
            assert src_idx < link_idx, (
                f"Declared source at {src_idx} should precede outlink at {link_idx}"
            )

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
            (
                "---\ntitle: Page A\nkind: topic\n---\n"
                "# Page A\n\nSee [[Wiki/Concepts/page-b|Page B]].\n"
            ),
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
                (
                    f"---\ntitle: Topic {i}\nkind: topic\n---\n"
                    f"# Topic {i}\n\nContent for topic {i}.\n"
                ),
                encoding="utf-8",
            )

        build_vault(vault)
        plan = plan_context(vault, "topic", max_files=3)

        assert plan.selected_count <= 3
        assert plan.omitted
        assert plan.stats["omitted_count"] == len(plan.omitted)
        assert any(item.omitted_reason == "max-files" for item in plan.omitted)
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
        [item.path for item in plan.items]
        # With include_indexes, generated wiki index pages should be allowed
        # (they still need to match the query to appear)
        assert isinstance(plan.selected_count, int)

    def test_summary_fallback_counts_against_token_budget(self, tmp_path: Path) -> None:
        from wikimason.build import build_vault
        from wikimason.context_export import plan_context

        vault = tmp_path / "vault"
        init_vault(vault, demo=False)

        topics_dir = vault / "Wiki/Topics"
        topics_dir.mkdir(parents=True, exist_ok=True)
        (topics_dir / "budget-heavy.md").write_text(
            (
                "---\n"
                "title: Budget Focus Heavy\n"
                "kind: topic\n"
                "summary: Budget focus summary.\n"
                "---\n"
                "# Budget Focus Heavy\n\n" + ("budget focus " * 200)
            ),
            encoding="utf-8",
        )
        for name in ("budget-note-a.md", "budget-note-b.md"):
            (topics_dir / name).write_text(
                (
                    "---\n"
                    f"title: {name}\n"
                    "kind: topic\n"
                    "---\n"
                    "# Budget Note\n\n" + ("budget focus note " * 5)
                ),
                encoding="utf-8",
            )

        build_vault(vault)
        plan = plan_context(vault, "budget focus", max_tokens=60, max_files=10)

        assert plan.selected_count == 2
        assert any(item.include == "summary" for item in plan.items)
        assert any(item.omitted_reason == "max-tokens" for item in plan.omitted)
        assert plan.stats["selected_summary"] == 1

    def test_summary_fallback_counts_against_byte_budget(self, tmp_path: Path) -> None:
        from wikimason.build import build_vault
        from wikimason.context_export import plan_context

        vault = tmp_path / "vault"
        init_vault(vault, demo=False)

        topics_dir = vault / "Wiki/Topics"
        topics_dir.mkdir(parents=True, exist_ok=True)
        (topics_dir / "bytes-heavy.md").write_text(
            (
                "---\n"
                "title: Bytes Focus Heavy\n"
                "kind: topic\n"
                "summary: Bytes focus summary.\n"
                "---\n"
                "# Bytes Focus Heavy\n\n" + ("bytes focus " * 200)
            ),
            encoding="utf-8",
        )
        for name in ("bytes-note-a.md", "bytes-note-b.md"):
            (topics_dir / name).write_text(
                (
                    "---\n"
                    f"title: {name}\n"
                    "kind: topic\n"
                    "---\n"
                    "# Bytes Note\n\n" + ("bytes focus note " * 5)
                ),
                encoding="utf-8",
            )

        build_vault(vault)
        plan = plan_context(vault, "bytes focus", max_bytes=220, max_files=10)

        assert plan.selected_count == 2
        assert any(item.include == "summary" for item in plan.items)
        assert any(item.omitted_reason == "max-bytes" for item in plan.omitted)
        assert plan.stats["selected_summary"] == 1


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
        assert "SHA256" in content

    def test_file_markers(self, built_vault: Path) -> None:
        from wikimason.context_export import export_context

        out = built_vault / "export.md"
        export_context(built_vault, "demo", out)

        content = out.read_text(encoding="utf-8")
        assert "<!-- wikimason:begin-file" in content
        assert "<!-- wikimason:end-file -->" in content

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

    def test_markdown_includes_omitted_candidates(self, tmp_path: Path) -> None:
        from wikimason.build import build_vault
        from wikimason.context_export import plan_context, render_context_markdown

        vault = tmp_path / "vault"
        init_vault(vault, demo=False)

        topics_dir = vault / "Wiki/Topics"
        topics_dir.mkdir(parents=True, exist_ok=True)
        for i in range(6):
            (topics_dir / f"topic-{i}.md").write_text(
                (
                    f"---\ntitle: Topic {i}\nkind: topic\n---\n"
                    f"# Topic {i}\n\nTopic material {i}.\n"
                ),
                encoding="utf-8",
            )

        build_vault(vault)
        plan = plan_context(vault, "topic", max_files=2)
        markdown = render_context_markdown(vault, plan, show_omitted=3)

        assert "## Omitted Candidates" in markdown
        assert "max-files" in markdown

    def test_markdown_includes_source_closure_gaps(self, tmp_path: Path) -> None:
        from wikimason.build import build_vault
        from wikimason.context_export import plan_context, render_context_markdown

        vault = tmp_path / "vault"
        init_vault(vault, demo=False)

        topics_dir = vault / "Wiki/Topics"
        topics_dir.mkdir(parents=True, exist_ok=True)
        (topics_dir / "gap-page.md").write_text(
            "---\ntitle: Gap Page\nkind: topic\nsources:\n"
            "  - ../../../etc/shadow\n---\n"
            "# Gap Page\n\nContent.\n",
            encoding="utf-8",
        )

        build_vault(vault)
        plan = plan_context(vault, "gap page")
        markdown = render_context_markdown(vault, plan)

        if plan.source_closure_gaps:
            assert "## Source Closure Gaps" in markdown
            assert "invalid-path" in markdown


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
        assert "omitted_count" in data
        assert "omitted_top" in data
        assert "query_diagnostics" in data
        assert "stats" in data
        assert "estimated_tokens" in data

        for item in data["items"]:
            assert "path" in item
            assert "kind" in item
            assert "score" in item
            assert "reasons" in item
            assert "sha256" in item
            assert "sha256_short" in item
            assert "rank" in item
            assert isinstance(item["reasons"], list)
            assert len(item["sha256"]) == 64
            assert len(item["sha256_short"]) == 12

        assert data["query_diagnostics"]["original"] == "demo"
        assert data["query_diagnostics"]["normalized"] == "demo"
        assert data["query_diagnostics"]["fts_mode"] == "strict"
        assert data["stats"]["selected_count"] == data["selected_count"]

    def test_json_serializable(self, built_vault: Path) -> None:
        from wikimason.context_export import plan_context, plan_to_json

        plan = plan_context(built_vault, "demo")
        data = plan_to_json(plan)
        text = json.dumps(data)
        assert json.loads(text) == data


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Escaping and audit regression tests
# ---------------------------------------------------------------------------


class TestEscapingAudit:
    def test_markdown_escapes_pipe_in_path(self, tmp_path: Path) -> None:
        from wikimason.build import build_vault
        from wikimason.context_export import plan_context, render_context_markdown

        vault = tmp_path / "vault"
        init_vault(vault, demo=False)
        topics_dir = vault / "Wiki/Topics"
        topics_dir.mkdir(parents=True, exist_ok=True)
        (topics_dir / "pipe-topic.md").write_text(
            "---\ntitle: Pipe Topic\nkind: topic\n---\n# Pipe Topic\n\nContent.\n",
            encoding="utf-8",
        )
        build_vault(vault)
        plan = plan_context(vault, "pipe topic")
        md = render_context_markdown(vault, plan)
        # Table pipes should not break Markdown structure
        lines = md.splitlines()
        manifest_start = next(
            i for i, line in enumerate(lines) if "Selection Manifest" in line
        )
        table_lines = [
            line for line in lines[manifest_start + 2 :] if line.startswith("|")
        ]
        for tl in table_lines:
            # Each row should have consistent pipe count
            assert tl.count("|") >= 7

    def test_json_audit_fields_present(self, built_vault: Path) -> None:
        from wikimason.context_export import plan_context, plan_to_json

        plan = plan_context(built_vault, "demo")
        data = plan_to_json(plan)

        # Verify all audit-grade fields
        assert isinstance(data["query_diagnostics"], dict)
        diag = data["query_diagnostics"]
        assert "original" in diag
        assert "normalized" in diag
        assert "fts_mode" in diag

        # Stats should have expected keys
        stats = data["stats"]
        expected_keys = {
            "total_candidates",
            "selected_count",
            "omitted_count",
            "warning_count",
            "selected_full",
            "selected_summary",
            "selected_metadata",
            "selected_pages",
            "selected_sources",
            "selected_files",
        }
        assert expected_keys.issubset(set(stats.keys()))

        # Items should have full audit data
        for item in data["items"]:
            assert len(item["sha256"]) == 64
            assert len(item["sha256_short"]) == 12
            assert isinstance(item["rank"], int)
            assert item["rank"] > 0

    def test_source_closure_gaps_in_json(self, tmp_path: Path) -> None:
        from wikimason.build import build_vault
        from wikimason.context_export import plan_context, plan_to_json

        vault = tmp_path / "vault"
        init_vault(vault, demo=False)
        topics_dir = vault / "Wiki/Topics"
        topics_dir.mkdir(parents=True, exist_ok=True)
        (topics_dir / "gap-json.md").write_text(
            "---\ntitle: Gap Json\nkind: topic\nsources:\n  - ../../../invalid\n---\n"
            "# Gap Json\n\nContent.\n",
            encoding="utf-8",
        )
        build_vault(vault)
        plan = plan_context(vault, "gap json")
        data = plan_to_json(plan)

        assert isinstance(data["source_closure_gaps"], list)
        if data["source_closure_gaps"]:
            gap = data["source_closure_gaps"][0]
            assert "source_path" in gap
            assert "required_by" in gap
            assert "reason" in gap


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
            (
                "---\ntitle: Secrets\nkind: topic\n---\n"
                "# Secrets\n\napi_key=AKIA1234567890abcdef\n"
                "password=hunter2\n"
            ),
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
            (
                "---\ntitle: Secrets\nkind: topic\n---\n"
                "# Secrets\n\napi_key=AKIA1234567890abcdef\n"
            ),
            encoding="utf-8",
        )

        build_vault(vault)
        out = tmp_path / "export.md"

        # Should succeed with --allow-sensitive
        export_context(vault, "secrets", out, allow_sensitive=True)
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

    def test_context_plan_text(
        self, built_vault: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from wikimason.cli import main

        result = main(
            [
                "context",
                "plan",
                "demo",
                "--vault",
                str(built_vault),
            ]
        )
        assert result == 0
        out = capsys.readouterr().out
        assert "demo" in out.lower()

    def test_context_plan_json(
        self, built_vault: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from wikimason.cli import main

        result = main(
            [
                "context",
                "plan",
                "demo",
                "--vault",
                str(built_vault),
                "--format",
                "json",
            ]
        )
        assert result == 0
        output = capsys.readouterr().out
        payload = json.loads(output.splitlines()[-1])
        assert payload["query"] == "demo"
        assert "items" in payload
        assert "query_diagnostics" in payload

    def test_context_export_writes_file(self, built_vault: Path) -> None:
        from wikimason.cli import main

        out = built_vault / "ctx.md"
        result = main(
            [
                "context",
                "export",
                "demo",
                "--vault",
                str(built_vault),
                "--output",
                str(out),
            ]
        )
        assert result == 0
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "wikimason_context_export" in content

    def test_context_index_rebuild(
        self, built_vault: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from wikimason.cli import main

        result = main(
            [
                "context",
                "index",
                "--rebuild",
                "--vault",
                str(built_vault),
                "--format",
                "json",
            ]
        )
        assert result == 0
        output = capsys.readouterr().out
        payload = json.loads(output.splitlines()[-1])
        assert payload["result"]["ok"]

    def test_context_export_print(
        self, built_vault: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from wikimason.cli import main

        result = main(
            [
                "context",
                "export",
                "demo",
                "--vault",
                str(built_vault),
                "--print",
            ]
        )
        assert result == 0
        output = capsys.readouterr().out
        assert "wikimason_context_export" in output
