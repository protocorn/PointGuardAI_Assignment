"""Terminal session for one signed-in synthetic employee."""

from __future__ import annotations

from assistant.catalog import Employee, load_documents, load_employees
from assistant.chat import initial_messages, run_turn
from assistant.tools import Session


def main() -> None:
    employees = load_employees()
    documents = load_documents()
    employee = _choose_employee(employees)
    session, messages = _start(employee)
    print("Commands: /reset  /switch  /quit")
    while True:
        try:
            user_text = input("\nYou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not user_text:
            continue
        command = user_text.casefold()
        if command == "/quit":
            return
        if command == "/reset":
            session, messages = _start(employee)
            print("Conversation and access requests cleared.")
            continue
        if command == "/switch":
            employee = _choose_employee(employees)
            session, messages = _start(employee)
            continue
        try:
            run_turn(messages, session, documents, user_text)
        except Exception as exc:
            print(f"Request failed: {exc}")


def _start(employee: Employee) -> tuple[Session, list[dict]]:
    _print_session(employee)
    return Session(employee=employee), initial_messages(employee)


def _print_session(employee: Employee) -> None:
    clearances = ", ".join(employee.can_read)
    print(
        f"Signed in as {employee.name} ({employee.id}), "
        f"role {employee.role}, can read: {clearances}"
    )


def _choose_employee(employees: list[Employee]) -> Employee:
    print("Sign in as a synthetic employee:")
    for index, employee in enumerate(employees, start=1):
        print(f"  {index}. {employee.name} — {employee.title} [{employee.role}]")
    while True:
        raw = input("Employee number: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(employees):
            return employees[int(raw) - 1]
        print("Enter a number from the list.")