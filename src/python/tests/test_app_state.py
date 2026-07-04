# Tests for app_state.py — global state, serialization, and agent orchestration.

import app_state as app_state_module
import pytest
from app_state import AppState
from phase import Phase


class FakeDB:
    async def search(self, **kwargs):
        return []


def make_state(monkeypatch, token=None):
    if token is None:
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    else:
        monkeypatch.setenv("GITHUB_TOKEN", token)
    return AppState(FakeDB())


# ----- construction ---------------------------------------------------------
def test_init_without_token(monkeypatch):
    state = make_state(monkeypatch)
    assert state.copilot_client.github_token is None
    assert state.agents == {}


def test_init_with_token(monkeypatch):
    state = make_state(monkeypatch, token="ghp_test")
    assert state.copilot_client.github_token == "ghp_test"


# ----- callbacks ------------------------------------------------------------
def test_notify_invokes_callbacks(monkeypatch):
    state = make_state(monkeypatch)
    hits = []
    state.register_update_callback(lambda: hits.append(1))
    state.notify_changed()
    assert hits == [1]


def test_notify_swallows_callback_errors(monkeypatch):
    state = make_state(monkeypatch)

    def boom():
        raise RuntimeError("callback failed")

    state.register_update_callback(boom)
    state.notify_changed()  # must not raise


# ----- agent registry -------------------------------------------------------
def _add_agent(state, agent_id="a1", enquiry="q", phase=Phase.DONE):
    from agent import Agent

    agent = Agent(agent_id, enquiry, state.property_database, lambda: None)
    agent.phase = phase
    state.agents[agent_id] = agent
    return agent


def test_get_agent_and_missing(monkeypatch):
    state = make_state(monkeypatch)
    agent = _add_agent(state, "x1")
    assert state.get_agent("x1") is agent
    with pytest.raises(KeyError):
        state.get_agent("nope")


def test_get_all_agents_sorted_by_start(monkeypatch):
    state = make_state(monkeypatch)
    a = _add_agent(state, "a")
    b = _add_agent(state, "b")
    # Force a deterministic ordering by started_at.
    from datetime import datetime, timedelta

    a.started_at = datetime.utcnow()
    b.started_at = a.started_at + timedelta(seconds=5)
    assert state.get_all_agents() == [a, b]


# ----- serialize_state ------------------------------------------------------
def test_serialize_state_basic(monkeypatch):
    state = make_state(monkeypatch)
    agent = _add_agent(state, "s1", enquiry="need a condo", phase=Phase.DONE)
    agent.report = "final report text"
    agent.current_intent = "Writing report"

    payload = state.serialize_state()
    assert "agents" in payload
    row = payload["agents"][0]
    assert row["id"] == "s1"
    assert row["enquiry"] == "need a condo"
    assert row["phase"] == "Done"
    assert row["report"] == "final report text"
    assert row["currentIntent"] == "Writing report"
    assert row["startedAt"] is not None


def test_serialize_state_non_string_intent(monkeypatch):
    state = make_state(monkeypatch)
    agent = _add_agent(state, "s2")
    agent.current_intent = object()  # non-string -> "Processing..."
    row = state.serialize_state()["agents"][0]
    assert row["currentIntent"] == "Processing..."


def test_serialize_state_report_none_when_not_string(monkeypatch):
    state = make_state(monkeypatch)
    agent = _add_agent(state, "s3")
    agent.report = 12345  # not a string
    row = state.serialize_state()["agents"][0]
    assert row["report"] is None


def test_serialize_state_handles_broken_agent(monkeypatch):
    state = make_state(monkeypatch)
    from datetime import datetime

    # An object whose .phase has no `.value` triggers the except fallback.
    broken = type(
        "Broken",
        (),
        {
            "id": "bad",
            "enquiry": "q",
            "current_intent": None,
            "phase": "NotAnEnum",  # str has no .value
            "report": None,
            "started_at": datetime.utcnow(),
            "finished_at": None,
        },
    )()
    state.agents["bad"] = broken
    row = state.serialize_state()["agents"][0]
    assert row["id"] == "bad"
    assert row["currentIntent"] == "Error"


# ----- run_agent_async ------------------------------------------------------
class FakeAgent:
    """Replaces the real Agent to control the outcome of run_async."""

    instances = []

    def __init__(self, agent_id, enquiry, database, update_ui):
        self.id = agent_id
        self.enquiry = enquiry
        self.phase = Phase.QUEUED
        self.started_at = __import__("datetime").datetime.utcnow()
        self.finished_at = None
        self.session = object()
        self._behavior = "done"
        FakeAgent.instances.append(self)

    async def run_async(self, client):
        if self._behavior == "raise":
            raise RuntimeError("agent crashed")
        self.phase = Phase.DONE if self._behavior == "done" else Phase.REJECTED_GARBAGE

    async def dispose_async(self):
        self.session = None


@pytest.fixture
def no_sleep(monkeypatch):
    async def instant(_seconds):
        return None

    monkeypatch.setattr(app_state_module.asyncio, "sleep", instant)


async def test_run_agent_done_keeps_agent(monkeypatch, no_sleep):
    FakeAgent.instances.clear()
    monkeypatch.setattr(app_state_module, "Agent", FakeAgent)
    state = make_state(monkeypatch)
    await state.run_agent_async("keep me")
    assert len(state.agents) == 1
    assert state.copilot_client.started is True


async def test_run_agent_rejected_is_removed(monkeypatch, no_sleep):
    FakeAgent.instances.clear()

    def rejecting(*args, **kwargs):
        agent = FakeAgent(*args, **kwargs)
        agent._behavior = "reject"
        return agent

    monkeypatch.setattr(app_state_module, "Agent", rejecting)
    state = make_state(monkeypatch)
    await state.run_agent_async("reject me")
    assert state.agents == {}


async def test_run_agent_exception_is_removed(monkeypatch, no_sleep):
    FakeAgent.instances.clear()

    def crashing(*args, **kwargs):
        agent = FakeAgent(*args, **kwargs)
        agent._behavior = "raise"
        return agent

    monkeypatch.setattr(app_state_module, "Agent", crashing)
    state = make_state(monkeypatch)
    await state.run_agent_async("crash me")
    assert state.agents == {}


async def test_run_agent_client_start_failure_returns_early(monkeypatch, no_sleep):
    state = make_state(monkeypatch)

    async def bad_start():
        raise RuntimeError("cannot start")

    monkeypatch.setattr(state.copilot_client, "start", bad_start)
    await state.run_agent_async("q")
    assert state.agents == {}  # never got created
