from __future__ import annotations

from app.agents.generic.base import ConfiguredAgent


class GenericDelegatorAgent(ConfiguredAgent):
    """Generic delegator for routing work to specialized agents or tools."""

