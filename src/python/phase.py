# ============================================================================
# phase.py - Definição de Fases do Pipeline
# ============================================================================
# Define os estados (fases) pelos quais um agente passa durante processamento.
# Também define a configuração visual do pipeline para a UI.
# ============================================================================

from dataclasses import dataclass
from enum import Enum

# ========== ENUM DE FASES ==========


class Phase(str, Enum):
    """
    Fases pelas quais um agente passa durante o processamento de uma consulta.
    """

    QUEUED = "Queued"  # Aguardando processamento
    VALIDATING = "Validating"  # Validando a consulta
    SEARCHING = "Searching"  # Buscando propriedades
    WRITING_REPORT = "WritingReport"  # Escrevendo relatório
    REJECTED_GARBAGE = "RejectedGarbage"  # Rejeitado: consulta inválida
    REJECTED_NO_MATCHES = "RejectedNoMatches"  # Rejeitado: sem resultados
    DONE = "Done"  # Concluído com sucesso


# ========== CONFIGURAÇÃO DO PIPELINE ==========


@dataclass
class PhaseNode:
    """
    Configuração de um nó (fase) no pipeline visual.
    Define posição, label e próximas fases possíveis.
    """

    label: str  # Texto exibido na UI
    col: int  # Coluna no grid (posição X)
    row: int  # Linha no grid (posição Y)
    next_phases: list[Phase]  # Fases para onde pode transitar
    is_finished: bool = False  # Se é uma fase final
    y_offset: int = 0  # Offset vertical (para fases na mesma coluna)


class PipelineConfig:
    """
    Configuração estática do pipeline de fases.
    Define layout visual e transições possíveis.
    """

    # Dicionário de nós do pipeline (Layout Vertical)
    NODES = {
        Phase.QUEUED: PhaseNode(label="Queued", col=0, row=0, next_phases=[Phase.VALIDATING]),
        Phase.VALIDATING: PhaseNode(
            label="Validating", col=0, row=1, next_phases=[Phase.SEARCHING, Phase.REJECTED_GARBAGE]
        ),
        Phase.SEARCHING: PhaseNode(
            label="Searching",
            col=0,
            row=2,
            next_phases=[Phase.WRITING_REPORT, Phase.REJECTED_NO_MATCHES],
        ),
        Phase.WRITING_REPORT: PhaseNode(
            label="Writing Report", col=0, row=3, next_phases=[Phase.DONE]
        ),
        Phase.REJECTED_GARBAGE: PhaseNode(
            label="Rejected (Garbage)", col=1, row=2, next_phases=[], is_finished=True, y_offset=0
        ),
        Phase.REJECTED_NO_MATCHES: PhaseNode(
            label="Rejected (No Matches)",
            col=1,
            row=3,
            next_phases=[],
            is_finished=True,
            y_offset=0,
        ),
        Phase.DONE: PhaseNode(label="Done", col=0, row=4, next_phases=[], is_finished=True),
    }

    # Lista de arestas (transições) do pipeline
    EDGES = [
        (Phase.QUEUED, Phase.VALIDATING),
        (Phase.VALIDATING, Phase.SEARCHING),
        (Phase.VALIDATING, Phase.REJECTED_GARBAGE),
        (Phase.SEARCHING, Phase.WRITING_REPORT),
        (Phase.SEARCHING, Phase.REJECTED_NO_MATCHES),
        (Phase.WRITING_REPORT, Phase.DONE),
    ]
