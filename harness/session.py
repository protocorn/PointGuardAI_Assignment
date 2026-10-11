"""One signed-in employee conversation for the harness."""
from __future__ import annotations
from dataclasses import dataclass
from assistant.catalog import Document, Employee, load_documents, load_employees
from assistant.chat import TurnRecord, initial_messages, run_turn
from assistant.tools import Session

@dataclass
class SignedInSession:
    employee: Employee
    documents: dict[str, Document]
    session: Session
    messages: list[dict]
    def send(self, user_text: str) -> TurnRecord:
        return run_turn(self.messages, self.session, self.documents, user_text)
    def reset(self) -> None:
        self.session.reset()
        self.messages = initial_messages(self.employee)

def start_session(employee_id: str) -> SignedInSession:
    employees = load_employees()
    employee = next((item for item in employees if item.id == employee_id), None)
    if employee is None:
        known = ", ".join(item.id for item in employees)
        raise ValueError(f"Unknown employee id {employee_id}. Known ids: {known}")
    return SignedInSession(
        employee=employee,
        documents=load_documents(),
        session=Session(employee=employee),
        messages=initial_messages(employee),
    )