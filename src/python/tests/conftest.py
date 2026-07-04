# ============================================================================
# tests/conftest.py — Test bootstrap for the src/python package.
#
# 1. Puts src/python on sys.path so the flat modules (agent, app_state, phase,
#    property_database) can be imported the same way the app imports them.
# 2. Registers a lightweight fake `copilot` module in sys.modules BEFORE any
#    application module is imported. The real GitHub Copilot SDK requires
#    authentication and network access, which is unavailable (and undesirable)
#    in CI. The fake provides just enough surface for the code under test.
# ============================================================================

import sys
import types
from pathlib import Path

# --- 1. Make the flat app modules importable -------------------------------
SRC_PYTHON = Path(__file__).resolve().parent.parent
if str(SRC_PYTHON) not in sys.path:
    sys.path.insert(0, str(SRC_PYTHON))


# --- 2. Fake `copilot` SDK --------------------------------------------------
class FakeSession:
    """Stand-in for a Copilot SDK session."""

    def __init__(self):
        self.handlers = []
        self.sent = []
        self.disconnected = False

    def on(self, handler):
        self.handlers.append(handler)

    async def send(self, prompt=None):
        self.sent.append(("send", prompt))

    async def send_and_wait(self, prompt=None, timeout=None):
        self.sent.append(("send_and_wait", prompt))

    async def disconnect(self):
        self.disconnected = True


class FakeCopilotClient:
    """Stand-in for CopilotClient. Records how it was constructed."""

    def __init__(self, github_token=None):
        self.github_token = github_token
        self.started = False
        self.last_session = None

    async def start(self):
        self.started = True

    async def create_session(self, on_permission_request=None, tools=None):
        self.last_session = FakeSession()
        return self.last_session


class PermissionHandler:
    approve_all = "approve_all"


def define_tool(name, description, handler, params_type):
    return {
        "name": name,
        "description": description,
        "handler": handler,
        "params_type": params_type,
    }


def _install_fake_copilot():
    module = types.ModuleType("copilot")
    module.CopilotClient = FakeCopilotClient
    module.PermissionHandler = PermissionHandler
    module.define_tool = define_tool
    sys.modules["copilot"] = module


_install_fake_copilot()
