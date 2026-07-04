import sys

sys.path.insert(0, "c:\\Github\\multiagent-copilotsdk-python\\src\\python")

from app import app
from fastapi.testclient import TestClient

client = TestClient(app)

try:
    response = client.get("/")
    print(f"Status: {response.status_code}")
    if response.status_code != 200:
        print(f"Error: {response.text}")
except Exception as e:
    print(f"Exception: {e}")
    import traceback

    traceback.print_exc()
