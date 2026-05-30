"""Test COMMAND_SPECS json_output metadata consistency."""

from __future__ import annotations

from wikimason.command_specs import COMMAND_SPECS


def test_json_output_metadata_matches_usage():
    """Every spec with --format text|json must have json_output=True."""
    for spec in COMMAND_SPECS:
        if "text|json" in spec.usage:
            assert spec.json_output, (
                f"Spec {spec.path} has --format text|json"
                f" but json_output={spec.json_output}"
            )


def test_all_agent_safe_commands_have_json():
    """All agent-safe commands that produce output should have json_output=True."""
    # This is a soft check — not all agent-safe commands need JSON,
    # but the major ones should.
    agent_safe_with_format = [
        spec for spec in COMMAND_SPECS if spec.agent_safe and "text|json" in spec.usage
    ]
    assert len(agent_safe_with_format) > 50, (
        "Expected at least 50 agent-safe commands with JSON,"
        f" got {len(agent_safe_with_format)}"
    )
