"""One signed-in employee conversation for the harness."""
from __future__ import annotations
from dataclasses import dataclass, field
from collections.abc import Callable

from assistant.catalog import Document, Employee, load_documents, load_employees
from assistant.chat import TurnRecord, initial_messages, run_turn
from assistant.tools import Session
from harness.progress import progress

@dataclass
class SignedInSession:
    employee: Employee
    documents: dict[str, Document]
    session: Session
    messages: list[dict]
    _baseline: dict[str, Document] = field(default_factory=dict)

    def send(self, user_text: str, on_progress: Callable[[str], None] | None = None) -> TurnRecord:
        def note(text: str) -> None:
            progress(f"target: {text}")
            if on_progress is not None:
                on_progress(text)

        return run_turn(self.messages, self.session, self.documents, user_text, on_progress=note)

    def plant(self, document_id: str, body: str) -> None:
        current = self.documents[document_id]
        self.documents[document_id] = Document(
            id=current.id,
            title=current.title,
            clearance=current.clearance,
            summary=current.summary,
            body=body,
        )

    def restore_documents(self) -> None:
        self.documents = dict(self._baseline)

    def reset(self) -> None:
        self.session.reset()
        self.messages = initial_messages(self.employee)
        self.restore_documents()

def start_session(employee_id: str) -> SignedInSession:
    employees = load_employees()
    employee = next((item for item in employees if item.id == employee_id), None)
    if employee is None:
        known = ", ".join(item.id for item in employees)
        raise ValueError(f"Unknown employee id {employee_id}. Known ids: {known}")
    documents = load_documents()
    return SignedInSession(
        employee=employee,
        documents=documents,
        session=Session(employee=employee),
        messages=initial_messages(employee),
        _baseline=dict(documents),
    )