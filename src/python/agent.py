# ============================================================================
# agent.py - Agente de IA que processa consultas de imóveis
# ============================================================================
# Este é o CORAÇÃO do sistema: um agente único que usa a IA do GitHub Copilot
# para processar consultas de clientes através de múltiplas fases.
# A IA decide autonomamente quando avançar entre as fases.
# Conversão de Agent.cs para Python
# ============================================================================

from collections.abc import Callable
from datetime import datetime
from typing import Any

from copilot import CopilotClient, PermissionHandler, define_tool
from phase import Phase
from property_database import PropertyDatabase
from pydantic import BaseModel, Field

# ========== MODELOS DE PARÂMETROS DAS FERRAMENTAS ==========
# O SDK gera o JSON schema a partir destes modelos, permitindo que a IA
# saiba quais argumentos passar para cada ferramenta.


class SetPhaseParams(BaseModel):
    phase: str = Field(
        description=(
            "The new phase. One of: validating, searching, writing_report, "
            "done, rejected_garbage, rejected_no_matches"
        )
    )


class ReportIntentParams(BaseModel):
    intent: str = Field(description="Short description of current intent (max 4 words)")


class SearchParams(BaseModel):
    city: str | None = Field(default=None, description="City to search in")
    min_bedrooms: int | None = Field(default=None, description="Minimum bedrooms")
    max_bedrooms: int | None = Field(default=None, description="Maximum bedrooms")
    min_bathrooms: int | None = Field(default=None, description="Minimum bathrooms")
    max_bathrooms: int | None = Field(default=None, description="Maximum bathrooms")
    min_price: int | None = Field(default=None, description="Minimum price")
    max_price: int | None = Field(default=None, description="Maximum price")
    property_type: str | None = Field(default=None, description="Property type e.g. house, condo")
    min_square_footage: int | None = Field(default=None, description="Minimum square footage")
    max_square_footage: int | None = Field(default=None, description="Maximum square footage")
    min_parking: int | None = Field(default=None, description="Minimum parking spaces")


class Agent:
    """
    Agente de IA que processa uma consulta de cliente através de um pipeline multi-fase.
    A IA gerencia autonomamente as transições entre fases usando ferramentas fornecidas.
    """

    def __init__(
        self, agent_id: str, enquiry: str, database: PropertyDatabase, update_ui: Callable[[], None]
    ):
        """
        Inicializa um novo agente.

        Args:
            agent_id: Identificador único do agente (8 caracteres hex)
            enquiry: Consulta do cliente em linguagem natural
            database: Banco de dados de propriedades para busca
            update_ui: Callback para notificar UI de mudanças
        """
        self.id = agent_id
        self.enquiry = enquiry
        self.database = database
        self.update_ui = update_ui

        # Estado do agente
        self.current_intent: str | None = None
        self.phase: Phase = Phase.QUEUED
        self.started_at: datetime = datetime.utcnow()
        self.finished_at: datetime | None = None

        # Relatório final gerado pela IA para o vendedor
        self.report: str | None = None

        # Histórico de eventos da sessão
        self.session_events: list[dict[str, Any]] = []

        # Sessão com o Copilot SDK (será criada em run_async)
        self.session = None

    async def run_async(self, client: CopilotClient):
        """
        Executa o agente completo: cria sessão com IA e processa a consulta.
        A IA lê as instruções e gerencia autonomamente as transições de fase.

        Args:
            client: Cliente do GitHub Copilot SDK autenticado
        """

        try:
            # --- 1. CONFIGURAR INSTRUÇÕES DO SISTEMA ---
            system_instructions = """
You are part of a real estate recommendation system. You will receive enquiries from customers,
and you must carry out the following workflow. As you proceed, you will update your current phase
and intent, which will be visible to the user. Do not stop until the phase reaches a final state.
Start by setting phase to "validating".

- Validation phase
  - Check the enquiry is genuine and not spam, garbage, or off-topic.
  - If it's not genuine, set phase to "rejected_garbage" and stop.
- Search phase
  - Extract relevant search criteria and search our property listings.
  - To search our property listings, call the search tool.
    You may call it multiple times with different filters to refine results.
  - If the customer is looking for a neighbourhood with a particular feature (such as schools)
    always perform at least one web search to confirm locations.
  - At the end of this phase, if you don't find any relevant properties, set phase to
    "rejected_no_matches" and stop. We are very busy and do not want to talk to any customers
    that don't match our offerings. Don't write reports for customers that won't convert.
- Report phase
  - Write up a report for our salesperson to use when calling the customer
  - Your report should include a summary of the customer's needs and the top 1-3 matching
    properties. For each property, include key selling points for this customer.
  - At the end of this phase, set phase to "done" and stop.

As you go, always use set_current_phase each time you enter a new phase, and report your
intent at each step.
"""

            # --- 2. DEFINIR FERRAMENTAS ---
            tools = [
                # Ferramenta para mudar fase
                define_tool(
                    name="set_current_phase",
                    description="Sets the current phase of the agent. Use this to report progress.",
                    handler=self.set_current_phase,
                    params_type=SetPhaseParams,
                ),
                # Ferramenta para reportar intenção
                define_tool(
                    name="report_intent",
                    description="Reports the current intent of the agent (max 4 words)",
                    handler=self.report_intent,
                    params_type=ReportIntentParams,
                ),
                # Ferramenta para buscar propriedades
                define_tool(
                    name="search",
                    description="Search for properties in the database",
                    handler=self.search_properties_wrapper,
                    params_type=SearchParams,
                ),
            ]

            # --- 3. CRIAR SESSÃO COM IA ---
            self.session = await client.create_session(
                on_permission_request=PermissionHandler.approve_all, tools=tools
            )

            # --- 4. REGISTRAR EVENTOS ---
            def handle_event(event):
                self._on_session_event(event)

            self.session.on(handle_event)

            # --- 5. ENVIAR INSTRUÇÕES E PROCESSAR CONSULTA ---
            await self.session.send(prompt=system_instructions)
            # timeout alto: o workflow completo (validar -> buscar -> relatório)
            # pode levar vários minutos com múltiplos turnos do modelo.
            await self.session.send_and_wait(
                prompt=f"<enquiry>{self.enquiry}</enquiry>",
                timeout=600.0,
            )

        except Exception as e:
            print(f"[AGENT {self.id}] ERROR: {e}", flush=True)
            # Só marca como rejeitado se ainda não chegou a um estado final
            if self.phase not in (
                Phase.DONE,
                Phase.REJECTED_GARBAGE,
                Phase.REJECTED_NO_MATCHES,
            ):
                self.phase = Phase.REJECTED_GARBAGE
            self.finished_at = datetime.utcnow()
            self.update_ui()

    def _on_session_event(self, event):
        """Callback chamado para cada evento da sessão (mensagens, tool calls, etc)"""
        try:
            # Serialização segura: converte objetos complexos para strings
            def safe_serialize(obj):
                if isinstance(obj, (str, int, float, bool, type(None))):
                    return obj
                elif isinstance(obj, (list, tuple)):
                    return [safe_serialize(item) for item in obj]
                elif isinstance(obj, dict):
                    return {k: safe_serialize(v) for k, v in obj.items()}
                elif hasattr(obj, "__dict__"):
                    return {
                        k: safe_serialize(v)
                        for k, v in obj.__dict__.items()
                        if not k.startswith("_")
                    }
                else:
                    return str(obj)

            event_dict = {
                "type": event.type.value if hasattr(event.type, "value") else str(event.type),
                "data": safe_serialize(event.data) if hasattr(event, "data") else None,
            }
            self.session_events.append(event_dict)

            # Captura o texto do relatório: mensagens do assistente com conteúdo.
            # O relatório final do vendedor é a mensagem mais longa do assistente;
            # mensagens curtas de status (ex: "Report complete.") não devem
            # sobrescrever o relatório completo.
            event_type = event.type.value if hasattr(event.type, "value") else str(event.type)
            if event_type == "assistant.message" and hasattr(event, "data"):
                content = getattr(event.data, "content", None)
                if isinstance(content, str) and content.strip():
                    if self.report is None or len(content) > len(self.report):
                        self.report = content
        except Exception as e:
            print(f"Error processing event: {e}")
        self.update_ui()

    # ========== FERRAMENTAS DA IA ==========

    def set_current_phase(self, params: SetPhaseParams, invocation) -> str:
        """
        FERRAMENTA: Permite a IA mudar a fase atual do pipeline.
        Exemplo: IA chama set_current_phase(phase="validating") para iniciar validação.

        Args:
            params: Parâmetros contendo a nova fase
            invocation: ToolInvocation do SDK

        Returns:
            Mensagem de confirmação
        """
        phase = self._parse_phase(params.phase)
        if phase is None:
            return f"Invalid phase: {params.phase}"
        self.phase = phase
        self.update_ui()
        return f"Phase set to {phase.value}"

    @staticmethod
    def _parse_phase(value: str) -> Phase | None:
        """
        Converte a string de fase da IA (ex: 'validating', 'writing_report')
        para o enum Phase, tolerando snake_case, minúsculas e o valor exato.
        """
        if not value:
            return None
        # Normaliza: remove underscores/espaços e coloca em minúsculo
        normalized = value.replace("_", "").replace(" ", "").lower()
        for phase in Phase:
            # Compara com o valor do enum normalizado (ex: "writingreport")
            if phase.value.replace("_", "").lower() == normalized:
                return phase
            # Compara com o nome do enum normalizado (ex: "writingreport")
            if phase.name.replace("_", "").lower() == normalized:
                return phase
        return None

    def report_intent(self, params: ReportIntentParams, invocation) -> str:
        """
        FERRAMENTA: Permite a IA reportar sua intenção atual em tempo real.
        Exemplo: IA chama report_intent(intent="Validating enquiry") para mostrar progresso.

        Args:
            params: Parâmetros contendo a intenção
            invocation: ToolInvocation do SDK

        Returns:
            Mensagem de confirmação
        """
        intent = params.intent
        if intent is None or not isinstance(intent, str):
            self.current_intent = "Processing..."
        else:
            self.current_intent = intent
        self.update_ui()
        return "Intent reported"

    async def search_properties_wrapper(
        self, params: SearchParams, invocation
    ) -> list[dict[str, Any]]:
        """
        FERRAMENTA: Wrapper assíncrono para busca de propriedades.
        A IA chama esta função para buscar propriedades no banco de dados.

        Args:
            params: Critérios de busca
            invocation: ToolInvocation do SDK

        Returns:
            Lista de propriedades que correspondem aos critérios
        """
        return await self.database.search(
            city=params.city,
            min_bedrooms=params.min_bedrooms,
            max_bedrooms=params.max_bedrooms,
            min_bathrooms=params.min_bathrooms,
            max_bathrooms=params.max_bathrooms,
            min_price=params.min_price,
            max_price=params.max_price,
            property_type=params.property_type,
            min_square_footage=params.min_square_footage,
            max_square_footage=params.max_square_footage,
            min_parking=params.min_parking,
        )

    async def dispose_async(self):
        """Libera recursos da sessão"""
        if self.session:
            try:
                await self.session.disconnect()
            except Exception as e:
                print(f"Error disconnecting session: {e}")
