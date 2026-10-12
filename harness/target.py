"""PyRIT target that sends user messages to one signed-in employee session."""

from __future__ import annotations

from assistant.chat import TurnRecord, dump_tool_exchanges
from harness.actions import document_was_reread
from harness.progress import progress
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
        preview = (request.converted_value or "").replace("\n", " ")[:80]
        progress(f"target: sending ({len(request.converted_value or '')} chars) {preview}")
        record = signed.send(request.converted_value)
        progress(f"target: reply received ({len(record.reply)} chars), tools={len(record.tool_exchanges)}")
        return [
            construct_response_from_request(
                request=request,
                response_text_pieces=[record.reply],
                prompt_metadata=_record_metadata(record, signed, request.converted_value or ""),
            )
        ]

    async def reset_conversation_async(self, *, conversation_id: str) -> None:
        signed = self._sessions.pop(conversation_id, None)
        if signed is not None:
            signed.reset()


class PlantingHarborlineTarget(HarborlineTarget):
    """Plant a junior document body before each user turn, then send."""

    def __init__(self, *, employee_id: str, plant_id: str, plants: list[str]) -> None:
        super().__init__(employee_id=employee_id)
        self._plant_id = plant_id
        self._plants = list(plants)
        self.document_edited = False
        self.document_reread = False

    @limit_requests_per_minute
    async def _send_prompt_to_target_async(
        self, *, normalized_conversation: list[Message]
    ) -> list[Message]:
        request = normalized_conversation[-1].get_piece()
        conversation_id = request.conversation_id or ""
        signed = self.session_for(conversation_id)
        if self._plants:
            signed.plant(self._plant_id, self._plants.pop(0))
            self.document_edited = True
            progress(f"target: planted {self._plant_id}")
        preview = (request.converted_value or "").replace("\n", " ")[:80]
        progress(f"target: sending ({len(request.converted_value or '')} chars) {preview}")
        record = signed.send(request.converted_value)
        progress(f"target: reply received ({len(record.reply)} chars), tools={len(record.tool_exchanges)}")
        if document_was_reread(record.tool_exchanges, self._plant_id):
            self.document_reread = True
        return [
            construct_response_from_request(
                request=request,
                response_text_pieces=[record.reply],
                prompt_metadata=_record_metadata(record, signed, request.converted_value or ""),
            )
        ]


def _record_metadata(
    record: TurnRecord, signed: SignedInSession, user_text: str = ""
) -> dict[str, str | int]:
    return {
        "employee_id": signed.employee.id,
        "session_role": signed.employee.role,
        "stopped_by_tool_limit": int(record.stopped_by_tool_limit),
        "tool_exchanges": dump_tool_exchanges(record.tool_exchanges),
        "user_message": user_text,
    }
