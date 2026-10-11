"""PyRIT target that sends user messages to one signed-in employee session."""

from __future__ import annotations

from assistant.chat import TurnRecord, dump_tool_exchanges
from harness.session import SignedInSession, start_session
from pyrit.models import Message, construct_response_from_request
from pyrit.prompt_target import PromptTarget
from pyrit.prompt_target.common.target_capabilities import TargetCapabilities
from pyrit.prompt_target.common.target_configuration import TargetConfiguration
from pyrit.prompt_target.common.utils import limit_requests_per_minute


class HarborlineTarget(PromptTarget):
    """One PyRIT conversation id maps to one employee session."""

    _DEFAULT_CONFIGURATION = TargetConfiguration(
        capabilities=TargetCapabilities(
            supports_multi_turn=True,
            supports_editable_history=True,
        )
    )

    def __init__(self, *, employee_id: str) -> None:
        super().__init__(model_name="assistant")
        self._employee_id = employee_id
        self._sessions: dict[str, SignedInSession] = {}

    def session_for(self, conversation_id: str) -> SignedInSession:
        signed = self._sessions.get(conversation_id)
        if signed is None:
            signed = start_session(self._employee_id)
            self._sessions[conversation_id] = signed
        return signed

    @limit_requests_per_minute
    async def _send_prompt_to_target_async(
        self, *, normalized_conversation: list[Message]
    ) -> list[Message]:
        request = normalized_conversation[-1].get_piece()
        conversation_id = request.conversation_id or ""
        signed = self.session_for(conversation_id)
        record = signed.send(request.converted_value)
        return [
            construct_response_from_request(
                request=request,
                response_text_pieces=[record.reply],
                prompt_metadata=_record_metadata(record, signed),
            )
        ]

    async def reset_conversation_async(self, *, conversation_id: str) -> None:
        signed = self._sessions.pop(conversation_id, None)
        if signed is not None:
            signed.reset()


def _record_metadata(record: TurnRecord, signed: SignedInSession) -> dict[str, str | int]:
    return {
        "employee_id": signed.employee.id,
        "session_role": signed.employee.role,
        "stopped_by_tool_limit": int(record.stopped_by_tool_limit),
        "tool_exchanges": dump_tool_exchanges(record.tool_exchanges),
    }
