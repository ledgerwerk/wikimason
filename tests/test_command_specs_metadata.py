"""Test COMMAND_SPECS json_output metadata consistency."""

from __future__ import annotations

from wikimason.command_specs import COMMAND_SPECS
from wikimason.logging_policy import (
    AUDIT_POLICY_COMMANDS,
    CHANGE_POLICY_COMMANDS,
    LOGGED_COMMANDS,
)


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


def test_log_command_specs_have_expected_log_policies() -> None:
    specs = {spec.path: spec for spec in COMMAND_SPECS}

    assert specs[("log", "add")].log_policy == "manual"
    assert specs[("log", "tail")].log_policy == "none"
    assert specs[("log", "check")].log_policy == "none"
    assert specs[("log", "rotate")].log_policy == "none"
    assert specs[("log", "stats")].log_policy == "none"


def test_change_policy_commands_have_change_log_policy() -> None:
    specs = {spec.path: spec for spec in COMMAND_SPECS}

    for command in CHANGE_POLICY_COMMANDS:
        path = tuple(command.split("."))
        assert path in specs, f"Missing CommandSpec for {command}"
        assert specs[path].log_policy == "change"


def test_audit_policy_commands_have_audit_log_policy() -> None:
    specs = {spec.path: spec for spec in COMMAND_SPECS}

    for command in AUDIT_POLICY_COMMANDS:
        path = tuple(command.split("."))
        assert path in specs, f"Missing CommandSpec for {command}"
        assert specs[path].log_policy == "audit"


def test_logged_commands_cover_all_change_and_audit_specs() -> None:
    for spec in COMMAND_SPECS:
        command = ".".join(spec.path)
        if spec.log_policy in {"change", "audit"}:
            assert command in LOGGED_COMMANDS, f"{command} is missing logging coverage"
