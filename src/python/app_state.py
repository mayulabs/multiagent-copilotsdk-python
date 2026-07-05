# ============================================================================
# app_state.py - Estado Global e Orquestrador de Agentes
# ============================================================================
# Este arquivo gerencia o estado compartilhado da aplicação e orquestra
# a criação e execução de múltiplos agentes simultaneamente.
# É um Singleton - existe apenas uma instância na aplicação.
# ============================================================================

import asyncio
import os
import uuid
from collections.abc import Callable
from datetime import datetime

from agent import Agent
from copilot import CopilotClient
from phase import Phase
from property_database import PropertyDatabase


class AppState:
    """
    Estado global da aplicação. Gerencia o cliente do Copilot SDK e todos os agentes ativos.
    Singleton injetado via FastAPI dependency injection.
    """

    def __init__(self, property_database: PropertyDatabase):
        """
        Inicializa o estado da aplicação.

        Args:
            property_database: Banco de dados de propriedades compartilhado
        """
        self.property_database = property_database

        # Cliente único do GitHub Copilot SDK compartilhado por todos os agentes
        # Lê token do ambiente ou usa GitHub CLI (gh auth login)
        github_token = os.getenv("GITHUB_TOKEN")
        self.copilot_client = (
            CopilotClient(github_token=github_token) if github_token else CopilotClient()
        )
        self._client_started = False

        # Dicionário de todos os agentes ativos (key = ID do agente, value = Agent)
        self.agents: dict[str, Agent] = {}

        # Lista de callbacks de atualização da UI
        self._update_callbacks: list[Callable[[], None]] = []

    def register_update_callback(self, callback: Callable[[], None]):
        """
        Registra um callback para ser notificado quando o estado mudar.
        Usado pelo WebSocket para enviar atualizações em tempo real.

        Args:
            callback: Função a ser chamada quando o estado mudar
        """
        self._update_callbacks.append(callback)

    def notify_changed(self):
        """
        Notifica todos os callbacks registrados que o estado mudou.
        Dispara re-renderização da UI via WebSocket.
        """
        for callback in self._update_callbacks:
            try:
                callback()
            except Exception as e:
                print(f"Error in update callback: {e}")

    async def run_agent_async(self, enquiry: str):
        """
        Cria e executa um novo agente para processar uma consulta de cliente.
        Este método é assíncrono e roda em background - não bloqueia a UI.

        Args:
            enquiry: Consulta do cliente em linguagem natural
        """
        # Inicia o cliente se necessário
        if not self._client_started:
            try:
                await self.copilot_client.start()
                self._client_started = True
                print("Copilot client started")
            except Exception as e:
                print(f"Error starting Copilot client: {e}")
                return

        # --- 1. GERAR ID ÚNICO ---
        # Cria um ID hexadecimal de 8 caracteres (ex: "a1b2c3d4")
        agent_id = uuid.uuid4().hex[:8]

        # --- 2. CRIAR NOVO AGENTE ---
        agent = Agent(agent_id, enquiry, self.property_database, self.notify_changed)

        # --- 3. REGISTRAR NO DICIONÁRIO ---
        self.agents[agent_id] = agent
        self.notify_changed()
        print(f"Created agent {agent_id}")

        try:
            # --- 4. EXECUTAR AGENTE ---
            # Chama Agent.run_async() que cria sessão com IA e processa tudo
            # Este await pode demorar minutos enquanto a IA trabalha
            await agent.run_async(self.copilot_client)

            # --- 5. MARCAR COMO FINALIZADO ---
            agent.finished_at = datetime.utcnow()
            self.notify_changed()

            # --- 6. DECIDIR SE REMOVE OU MANTÉM ---
            if agent.phase == Phase.DONE:
                # ✅ SUCESSO: Agente completou com sucesso, deixa na tela
                return

            # ❌ REJEITADO: Agente foi rejeitado (spam ou sem resultados)
            # Aguarda 15 segundos para o usuário ver, depois remove
            await asyncio.sleep(15)
            if agent_id in self.agents:
                del self.agents[agent_id]
                await agent.dispose_async()
            self.notify_changed()

        except Exception as e:
            print(f"Error running agent {agent_id}: {e}")
            import traceback

            traceback.print_exc()
            agent.finished_at = datetime.utcnow()
            self.notify_changed()

            # Remove após erro
            await asyncio.sleep(15)
            if agent_id in self.agents:
                del self.agents[agent_id]
                if agent.session:
                    await agent.dispose_async()
            self.notify_changed()

    def get_agent(self, agent_id: str) -> Agent:
        """
        Retorna um agente pelo ID.

        Args:
            agent_id: ID do agente

        Returns:
            Instância do agente

        Raises:
            KeyError: Se o agente não existir
        """
        return self.agents[agent_id]

    def get_all_agents(self) -> list[Agent]:
        """
        Retorna lista de todos os agentes ativos.

        Returns:
            Lista de agentes ordenada por data de criação
        """
        return sorted(self.agents.values(), key=lambda a: a.started_at)

    def serialize_state(self) -> dict:
        """
        Serializa o estado completo para enviar via WebSocket.

        Returns:
            Dicionário com estado de todos os agentes
        """

        agents_list = []
        for agent in self.get_all_agents():
            try:
                # Sanitiza current_intent - garante que seja string ou None
                current_intent_value = None
                if agent.current_intent:
                    if isinstance(agent.current_intent, str):
                        current_intent_value = agent.current_intent
                    else:
                        # Se for um objeto (como ToolInvocation), tenta extrair algo útil
                        current_intent_value = "Processing..."

                # Converte explicitamente tudo para tipos básicos
                agent_dict = {
                    "id": str(agent.id),
                    "enquiry": str(agent.enquiry),
                    "currentIntent": current_intent_value,
                    "phase": str(agent.phase.value),
                    "report": agent.report if isinstance(agent.report, str) else None,
                    "startedAt": agent.started_at.isoformat() if agent.started_at else None,
                    "finishedAt": agent.finished_at.isoformat() if agent.finished_at else None,
                    "sessionEvents": [],  # Não enviamos eventos por serem complexos
                }
                agents_list.append(agent_dict)
            except Exception as e:
                print(f"[ERROR] Failed to serialize agent {agent.id}: {e}")
                # Adiciona versão simplificada em caso de erro
                agents_list.append(
                    {
                        "id": str(agent.id),
                        "enquiry": str(agent.enquiry),
                        "currentIntent": "Error",
                        "phase": "Queued",
                        "startedAt": datetime.utcnow().isoformat(),
                        "finishedAt": None,
                        "sessionEvents": [],
                    }
                )

        return {"agents": agents_list}
