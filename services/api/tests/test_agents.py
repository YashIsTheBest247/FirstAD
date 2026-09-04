"""Tests for how the crew is constructed.

The safety configuration is here because it is easy to lose in a refactor and
expensive to lose: these agents read screenplays, and drama is made of exactly
what default filters catch. A refusal is not transient, so the retry path will
not rescue it.
"""

from __future__ import annotations

from google.genai import types

from app.agents.crew import CREW_ROLES, build_crew


def test_nine_agents_are_built() -> None:
    assert len(build_crew()) == 9


def test_every_agent_maps_to_a_named_crew_role() -> None:
    """The roster is not decoration; each agent stands in for a real job."""
    crew = build_crew()
    assert set(crew) == set(CREW_ROLES)


def test_every_agent_carries_an_output_schema() -> None:
    """The typed contract is what makes a seven-stage pipeline deterministic."""
    for name, agent in build_crew().items():
        assert agent.output_schema is not None, f"{name} has no output_schema"


def test_every_agent_relaxes_safety_thresholds() -> None:
    """A breakdown agent must be able to tag the props in a fight scene."""
    expected = {
        types.HarmCategory.HARM_CATEGORY_HARASSMENT,
        types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
        types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
    }

    for name, agent in build_crew().items():
        config = agent.generate_content_config
        assert config is not None, f"{name} has no generation config"

        settings = config.safety_settings or []
        assert {s.category for s in settings} == expected, f"{name} misses a category"

        for setting in settings:
            # Not BLOCK_NONE or OFF: loose enough for professional creative
            # material, still refusing what is genuinely egregious.
            assert setting.threshold is types.HarmBlockThreshold.BLOCK_ONLY_HIGH


def test_agents_cannot_hand_control_to_a_peer() -> None:
    """An agent that owes a typed answer must return it, not delegate."""
    for name, agent in build_crew().items():
        assert agent.disallow_transfer_to_parent is True, name
        assert agent.disallow_transfer_to_peers is True, name
