# Tests for agent.py — AI tool handlers, phase parsing, and session lifecycle.

from types import SimpleNamespace

import pytest
from agent import Agent, ReportIntentParams, SearchParams, SetPhaseParams
from phase import Phase


class FakeDB:
    def __init__(self, result=None):
        self.result = result if result is not None else [{"id": 1}]
        self.called_with = None

    async def search(self, **kwargs):
        self.called_with = kwargs
        return self.result


class RaisingClient:
    async def create_session(self, on_permission_request=None, tools=None):
        raise RuntimeError("boom")


def make_agent(db=None):
    calls = {"count": 0}

    def update_ui():
        calls["count"] += 1

    agent = Agent("abc123", "3-bed house in Toronto", db or FakeDB(), update_ui)
    agent._ui_calls = calls
    return agent


# ----- set_current_phase ----------------------------------------------------
def test_set_current_phase_valid():
    agent = make_agent()
    msg = agent.set_current_phase(SetPhaseParams(phase="validating"), None)
    assert agent.phase == Phase.VALIDATING
    assert "Validating" in msg


def test_set_current_phase_invalid():
    agent = make_agent()
    msg = agent.set_current_phase(SetPhaseParams(phase="not_a_phase"), None)
    assert agent.phase == Phase.QUEUED
    assert "Invalid phase" in msg


# ----- _parse_phase ---------------------------------------------------------
@pytest.mark.parametrize(
    "value,expected",
    [
        ("", None),
        ("writing_report", Phase.WRITING_REPORT),
        ("Writing Report", Phase.WRITING_REPORT),
        ("Done", Phase.DONE),
        ("rejected_no_matches", Phase.REJECTED_NO_MATCHES),
        ("searching", Phase.SEARCHING),
        ("garbage_value", None),
    ],
)
def test_parse_phase(value, expected):
    assert Agent._parse_phase(value) == expected


# ----- report_intent --------------------------------------------------------
def test_report_intent_string():
    agent = make_agent()
    agent.report_intent(ReportIntentParams(intent="Validating enquiry"), None)
    assert agent.current_intent == "Validating enquiry"


def test_report_intent_non_string_falls_back():
    agent = make_agent()
    # Duck-typed params with a non-string intent to hit the fallback branch.
    agent.report_intent(SimpleNamespace(intent=123), None)
    assert agent.current_intent == "Processing..."


# ----- search wrapper -------------------------------------------------------
async def test_search_wrapper_delegates_to_db():
    db = FakeDB(result=[{"id": 42}])
    agent = make_agent(db)
    out = await agent.search_properties_wrapper(SearchParams(city="Toronto", min_bedrooms=3), None)
    assert out == [{"id": 42}]
    assert db.called_with["city"] == "Toronto"
    assert db.called_with["min_bedrooms"] == 3


# ----- _on_session_event ----------------------------------------------------
def _event(event_type, content=None, data=None):
    if data is None and content is not None:
        data = SimpleNamespace(content=content)
    return SimpleNamespace(type=SimpleNamespace(value=event_type), data=data)


def test_event_captures_assistant_report():
    agent = make_agent()
    agent._on_session_event(_event("assistant.message", content="short"))
    agent._on_session_event(_event("assistant.message", content="a much longer final report"))
    assert agent.report == "a much longer final report"


def test_event_short_message_does_not_overwrite_longer_report():
    agent = make_agent()
    agent._on_session_event(_event("assistant.message", content="a much longer final report"))
    agent._on_session_event(_event("assistant.message", content="Done."))
    assert agent.report == "a much longer final report"


def test_event_type_without_value_attribute():
    agent = make_agent()
    # event.type is a plain string (no .value) -> str(event.type) path.
    evt = SimpleNamespace(type="assistant.message", data=SimpleNamespace(content="hello"))
    agent._on_session_event(evt)
    assert agent.report == "hello"


def test_event_non_assistant_is_not_captured():
    agent = make_agent()
    agent._on_session_event(_event("tool.call", data=SimpleNamespace(name="search")))
    assert agent.report is None


def test_event_serializes_nested_data():
    agent = make_agent()
    nested = SimpleNamespace(items=[1, "two", {"k": "v"}], _private="hidden")
    agent._on_session_event(_event("tool.result", data=nested))
    assert agent.session_events  # something was recorded
    recorded = agent.session_events[-1]["data"]
    assert "_private" not in recorded  # underscored attrs are dropped


def test_event_bad_object_is_handled():
    agent = make_agent()
    # None has no .type -> the handler must swallow the error, not crash.
    agent._on_session_event(None)
    assert agent._ui_calls["count"] >= 1  # update_ui still fired


# ----- run_async ------------------------------------------------------------
async def test_run_async_happy_path():
    from conftest import FakeCopilotClient

    agent = make_agent()
    client = FakeCopilotClient()
    await agent.run_async(client)
    # Session was created and prompts were sent.
    assert client.last_session is not None
    kinds = [k for k, _ in client.last_session.sent]
    assert "send" in kinds and "send_and_wait" in kinds


async def test_run_async_error_sets_rejected():
    agent = make_agent()
    await agent.run_async(RaisingClient())
    assert agent.phase == Phase.REJECTED_GARBAGE
    assert agent.finished_at is not None


async def test_run_async_error_keeps_existing_final_phase():
    agent = make_agent()
    agent.phase = Phase.DONE
    await agent.run_async(RaisingClient())
    assert agent.phase == Phase.DONE  # not downgraded to rejected


# ----- dispose_async --------------------------------------------------------
async def test_dispose_disconnects_session():
    from conftest import FakeSession

    agent = make_agent()
    agent.session = FakeSession()
    await agent.dispose_async()
    assert agent.session.disconnected is True


async def test_dispose_without_session_is_noop():
    agent = make_agent()
    agent.session = None
    await agent.dispose_async()  # must not raise


async def test_dispose_swallows_disconnect_errors():
    class BadSession:
        async def disconnect(self):
            raise RuntimeError("cannot disconnect")

    agent = make_agent()
    agent.session = BadSession()
    await agent.dispose_async()  # must not raise
