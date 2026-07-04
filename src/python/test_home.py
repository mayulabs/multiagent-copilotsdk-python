import asyncio
import sys

sys.path.insert(0, "c:\\Github\\multiagent-copilotsdk-python\\src\\python")

from app import home
from app_state import AppState
from property_database import PropertyDatabase


class FakeRequest:
    def __init__(self):
        self.app = type("obj", (object,), {"state": type("obj", (object,), {})})()


async def test():
    try:
        # Inicializar banco de dados
        db = PropertyDatabase("test.db")
        await db.initialize()
        await db.seed_data()

        # Criar request falso
        req = FakeRequest()
        req.app.state.property_database = db
        req.app.state.app_state = AppState(db)

        # Testar rota
        result = await home(req)
        print("Success!")
        print(f"Result type: {type(result)}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test())
