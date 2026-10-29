"""Read -> deterministic assessment -> validated proposal, without actuation."""

from dataclasses import dataclass

from ares.intelligence.decisions import Decision, ProposalEngine
from ares.supervisor import Assessment, Supervisor


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    assessment: Assessment
    proposal: Decision


class AnalysisPipeline:
    """Compose a trusted observation and an untrusted model recommendation."""

    def __init__(self, supervisor: Supervisor, proposals: ProposalEngine) -> None:
        self._supervisor = supervisor
        self._proposals = proposals

    def analyze(self, *, agent_id: str, tool_id: str) -> AnalysisResult:
        assessment = self._supervisor.assess(agent_id=agent_id, tool_id=tool_id)
        proposal = self._proposals.propose(assessment)
        return AnalysisResult(assessment=assessment, proposal=proposal)
