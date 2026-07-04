# Tests for phase.py — pipeline phase enum and static pipeline configuration.

from phase import Phase, PhaseNode, PipelineConfig


def test_phase_values_are_stable():
    # These string values are serialized to the frontend and must not drift.
    assert Phase.QUEUED.value == "Queued"
    assert Phase.VALIDATING.value == "Validating"
    assert Phase.SEARCHING.value == "Searching"
    assert Phase.WRITING_REPORT.value == "WritingReport"
    assert Phase.REJECTED_GARBAGE.value == "RejectedGarbage"
    assert Phase.REJECTED_NO_MATCHES.value == "RejectedNoMatches"
    assert Phase.DONE.value == "Done"


def test_phase_is_str_enum():
    # Phase(str, Enum) so `.value` and direct string comparison both work.
    assert Phase.DONE == "Done"
    assert isinstance(Phase.DONE.value, str)


def test_phase_node_defaults():
    node = PhaseNode(label="X", col=1, row=2, next_phases=[Phase.DONE])
    assert node.is_finished is False
    assert node.y_offset == 0
    assert node.next_phases == [Phase.DONE]


def test_pipeline_nodes_cover_every_phase():
    # Every phase must have a node so the UI can render it.
    for phase in Phase:
        assert phase in PipelineConfig.NODES


def test_pipeline_terminal_phases_are_finished():
    for terminal in (Phase.DONE, Phase.REJECTED_GARBAGE, Phase.REJECTED_NO_MATCHES):
        assert PipelineConfig.NODES[terminal].is_finished is True
        assert PipelineConfig.NODES[terminal].next_phases == []


def test_pipeline_edges_match_node_transitions():
    # Every declared edge must correspond to a valid next_phase on its source.
    for from_phase, to_phase in PipelineConfig.EDGES:
        assert to_phase in PipelineConfig.NODES[from_phase].next_phases


def test_validating_can_branch_to_search_or_rejection():
    nexts = PipelineConfig.NODES[Phase.VALIDATING].next_phases
    assert Phase.SEARCHING in nexts
    assert Phase.REJECTED_GARBAGE in nexts
