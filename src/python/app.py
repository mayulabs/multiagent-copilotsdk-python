# ============================================================================
# app.py - Ponto de Entrada da Aplicação FastAPI
# ============================================================================
# Este é o arquivo principal que inicializa a aplicação web FastAPI.
# Configura serviços, banco de dados, WebSockets e inicia o servidor.
# Equivalente ao Program.cs do ASP.NET Core.
# ============================================================================

import asyncio
import json
from contextlib import asynccontextmanager

from app_state import AppState
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from phase import PipelineConfig
from property_database import PropertyDatabase

# ========== LIFESPAN CONTEXT MANAGER ==========
# Gerencia inicialização e finalização da aplicação


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerencia o ciclo de vida da aplicação.
    Inicializa o banco de dados na startup.
    """
    # --- STARTUP ---
    print("Initializing database...")
    db = PropertyDatabase("properties.db")
    await db.initialize()
    await db.seed_data()

    # Cria estado global da aplicação
    app.state.property_database = db
    app.state.app_state = AppState(db)

    print("Application started successfully")
    print("Visit http://localhost:8000 to view the app")

    yield

    # --- SHUTDOWN ---
    print("Application shutting down...")


# ========== CRIAR APLICAÇÃO FASTAPI ==========

app = FastAPI(
    title="Agent Orchestrator",
    description="Multi-agent property search system powered by GitHub Copilot SDK",
    version="1.0.0",
    lifespan=lifespan,
)

# ========== CONFIGURAR TEMPLATES E ARQUIVOS ESTÁTICOS ==========

templates = Jinja2Templates(directory="templates")

# Monta diretório de arquivos estáticos (CSS, JS)
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except RuntimeError:
    # Diretório não existe ainda, será criado depois
    pass


# ========== ROTAS HTTP ==========


@app.get("/test")
async def test():
    """Endpoint de teste simples"""
    return {"status": "ok", "message": "Server is running!"}


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """
    Página principal da aplicação.
    Renderiza o template HTML com configuração do pipeline.
    """
    pipeline_config = {
        "nodes": {
            phase.value: {
                "label": node.label,
                "col": node.col,
                "row": node.row,
                "next": [p.value for p in node.next_phases],
                "isFinished": node.is_finished,
                "yOffset": node.y_offset,
            }
            for phase, node in PipelineConfig.NODES.items()
        },
        "edges": [
            {"from": from_phase.value, "to": to_phase.value}
            for from_phase, to_phase in PipelineConfig.EDGES
        ],
    }

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "pipeline_config_json": json.dumps(pipeline_config),
        },
    )


@app.post("/api/agents")
async def create_agent(request: Request):
    """
    Endpoint para criar um novo agente.
    Recebe uma consulta e inicia o processamento em background.
    """
    data = await request.json()
    enquiry = data.get("enquiry", "").strip()

    if not enquiry:
        return {"error": "Enquiry is required"}, 400

    # Inicia agente em background (não aguarda conclusão)
    app_state: AppState = request.app.state.app_state
    asyncio.create_task(app_state.run_agent_async(enquiry))

    return {"status": "Agent created"}


# ========== WEBSOCKET PARA ATUALIZAÇÕES EM TEMPO REAL ==========

active_websockets = set()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket para comunicação em tempo real com o frontend.
    Envia atualizações do estado sempre que um agente muda de fase.
    Equivalente ao SignalR/Blazor Server do ASP.NET Core.
    """
    print("[WS] Accepting WebSocket connection...", flush=True)
    await websocket.accept()
    active_websockets.add(websocket)
    print(f"[WS] WebSocket connected! Total connections: {len(active_websockets)}", flush=True)

    app_state: AppState = websocket.app.state.app_state

    # Callback para enviar atualizações - agora async-safe
    async def send_update_async():
        """Envia estado atualizado para o cliente"""
        try:
            if websocket in active_websockets:
                await websocket.send_json(app_state.serialize_state())
        except Exception as e:
            print(f"Error sending update: {e}")
            active_websockets.discard(websocket)

    # Wrapper síncrono para o callback
    def send_update():
        asyncio.create_task(send_update_async())

    # Registra callback no AppState
    app_state.register_update_callback(send_update)

    # Envia estado inicial
    try:
        await websocket.send_json(app_state.serialize_state())
    except Exception as e:
        print(f"Error sending initial state: {e}")
        active_websockets.discard(websocket)
        return

    try:
        # Mantém conexão aberta e aguarda mensagens do cliente
        print("[WS] Entering message loop...", flush=True)
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            print(f"[WS] Message received: {message}", flush=True)

            # Cliente pode enviar comandos via WebSocket
            if message.get("type") == "create_agent":
                enquiry = message.get("enquiry", "").strip()
                print(f"[WS] Creating agent with enquiry: {enquiry}", flush=True)
                if enquiry:
                    try:
                        asyncio.create_task(app_state.run_agent_async(enquiry))
                        print("[WS] Agent task created successfully", flush=True)
                    except Exception as agent_error:
                        print(f"[ERROR] Failed to create agent task: {agent_error}", flush=True)
                        import traceback

                        traceback.print_exc()

    except WebSocketDisconnect:
        active_websockets.discard(websocket)
        print("Client disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")
        import traceback

        traceback.print_exc()
        active_websockets.discard(websocket)


# ========== ROTAS DE API PARA DADOS ==========


@app.get("/api/agents")
async def get_agents(request: Request):
    """
    Retorna lista de todos os agentes ativos.
    """
    app_state: AppState = request.app.state.app_state
    return app_state.serialize_state()


@app.get("/api/agents/{agent_id}")
async def get_agent(agent_id: str, request: Request):
    """
    Retorna detalhes de um agente específico.
    """
    app_state: AppState = request.app.state.app_state
    try:
        agent = app_state.get_agent(agent_id)
        return {
            "id": agent.id,
            "enquiry": agent.enquiry,
            "currentIntent": agent.current_intent,
            "phase": agent.phase.value,
            "startedAt": agent.started_at.isoformat(),
            "finishedAt": agent.finished_at.isoformat() if agent.finished_at else None,
            "sessionEvents": agent.session_events,
        }
    except KeyError:
        return {"error": "Agent not found"}, 404


# ========== AMOSTRAS DE CONSULTAS ==========

SAMPLE_ENQUIRIES = [
    "I want a 3-bedroom house in Toronto with a backyard",
    "Looking for a condo in Vancouver under $500,000",
    "Need a family home near good schools in Calgary",
    "Want a waterfront property with 4+ bedrooms",
    "Looking for a starter home for first-time buyer",
    "Need parking for 2 cars in downtown area",
]


@app.get("/api/samples")
async def get_samples():
    """
    Retorna lista de consultas de exemplo.
    """
    return {"samples": SAMPLE_ENQUIRIES}


# ========== EXECUTAR SERVIDOR ==========

if __name__ == "__main__":
    import uvicorn

    # Demo server: binds to all interfaces so the app is reachable from the
    # host/container. Not for production exposure without a reverse proxy.
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)  # nosec B104
