"""Native Ollama chat target. Used for the attacker so think can stay on."""

from __future__ import annotations

import json
import urllib.request

from assistant.chat import MODEL, OLLAMA_URL
from harness.progress import progress
from pyrit.models import Message, construct_response_from_request
from pyrit.prompt_target import PromptTarget
from pyrit.prompt_target.common.target_capabilities import TargetCapabilities
from pyrit.prompt_target.common.target_configuration import TargetConfiguration
from pyrit.prompt_target.common.utils import limit_requests_per_minute

ATTACKER_TEMPERATURE = 0.7


class OllamaThinkTarget(PromptTarget):
    """One native /api/chat call with think enabled."""

    _DEFAULT_CONFIGURATION = TargetConfiguration(
        capabilities=TargetCapabilities(
            supports_multi_turn=True,
            supports_editable_history=True,
            supports_system_prompt=True,
        )
    )

    def __init__(self, *, temperature: float = ATTACKER_TEMPERATURE, think: bool = True) -> None:
        super().__init__(model_name=MODEL)
        self._temperature = temperature
        self._think = think

    @limit_requests_per_minute
    async def _send_prompt_to_target_async(
        self, *, normalized_conversation: list[Message]
    ) -> list[Message]:
        request = normalized_conversation[-1].get_piece()
        progress(f"attacker: waiting for {MODEL}")
        payload = {
            "model": MODEL,
            "messages": _ollama_messages(normalized_conversation),
            "stream": False,
            "think": self._think,
            "options": {"temperature": self._temperature, "num_predict": 1024},
        }
        http_request = urllib.request.Request(
            OLLAMA_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(http_request, timeout=120) as response:
            body = json.loads(response.read().decode("utf-8"))
        text = (body.get("message") or {}).get("content") or ""
        progress(f"attacker: reply received ({len(text)} chars)")
        return [
            construct_response_from_request(
                request=request,
                response_text_pieces=[text],
            )
        ]


def ollama_chat(
    *,
    system: str,
    user: str,
    temperature: float = ATTACKER_TEMPERATURE,
    think: bool = True,
) -> str:
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "think": think,
        "options": {"temperature": temperature, "num_predict": 1024},
    }
    progress(f"attacker: waiting for {MODEL}")
    request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        body = json.loads(response.read().decode("utf-8"))
    text = (body.get("message") or {}).get("content") or ""
    progress(f"attacker: reply received ({len(text)} chars)")
    return text


def _ollama_messages(conversation: list[Message]) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    for item in conversation:
        piece = item.get_piece()
        role = piece.role if piece.role in {"system", "user", "assistant"} else "user"
        messages.append({"role": role, "content": piece.converted_value or ""})
    return messages
