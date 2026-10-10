"""Tools available to the assistant.
Access is enforced here. The session employee comes from the application.
A role, clearance, or employee id supplied by the model is ignored.
Documents outside can_read are omitted entirely: no title, summary, or body.
"""

import json
from dataclasses import dataclass, field

from assistant.catalog import Employee, Document


@dataclass
class Session:
    employee: Employee
    requests: list[dict[str, str]] = field(default_factory=list)
    _next_request_number: int = 1

    def reset(self) -> None:
        self.requests.clear()
        self._next_request_number = 1


def list_documents(session: Session, documents: dict[str, Document], arguments: dict) -> dict:
    listed = []
    for document in documents.values():
        if document.clearance in session.employee.can_read:
            listed.append(
                {
                    "id": document.id,
                    "title": document.title,
                    "clearance": document.clearance,
                    "summary": document.summary,
                }
            )
        else:
            listed.append(
                {
                    "id": document.id,
                    "title": "[masked]",
                    "clearance": document.clearance,
                    "summary": "[masked]",
                }
            )
    return {"status": "ok", "documents": listed}


def read_document(session: Session, documents: dict[str, Document], arguments: dict) -> dict:
    document_id = str(arguments.get("document_id") or "").strip().upper()
    document = documents.get(document_id)
    if document is None:
        return {"status": "not_found", "document_id": document_id}
    if document.clearance not in session.employee.can_read:
        return {
            "status": "denied",
            "document_id": document.id,
            "required_clearance": document.clearance,
            "session_role": session.employee.role,
        }
    return {
        "status": "ok",
        "document_id": document.id,
        "title": document.title,
        "clearance": document.clearance,
        "summary": document.summary,
        "body": document.body,
    }

def submit_access_request(session: Session, documents: dict[str, Document], arguments: dict) -> dict:
    document_id = str(arguments.get("document_id") or "").strip().upper()
    reason = str(arguments.get("reason") or "").strip()
    if document_id not in documents:
        return {"status": "not_found", "document_id": document_id}
    if not reason:
        return {"status": "missing_reason", "document_id": document_id}
    request_id = f"R-{session._next_request_number}"
    session._next_request_number += 1
    session.requests.append(
        {
            "request_id": request_id,
            "document_id": document_id,
            "reason": reason,
            "employee_id": session.employee.id,
        }
    )
    return {
        "status": "filed",
        "request_id": request_id,
        "document_id": document_id,
        "filed_by": session.employee.id,
    }


TOOLS = {
    "list_documents": list_documents,
    "read_document": read_document,
    "submit_access_request": submit_access_request,
}


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "list_documents",
            "description": "List documents the signed-in employee is allowed to read. Optional query matches title or summary.",
            "parameters": {
                "type": "object",
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_document",
            "description": "Read one document the signed-in employee is allowed to read. Returns a denial with no document text when the clearance is too high.",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_id": {"type": "string", "description": "Document id, such as DOC-101."}
                },
                "required": ["document_id"],
            },
        },
    },
{
        "type": "function",
        "function": {
            "name": "submit_access_request",
            "description": "File a request for a document. This does not grant access and does not return the document.",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_id": {"type": "string", "description": "Document id being requested."},
                    "reason": {"type": "string", "description": "Why the employee wants access."},
                },
                "required": ["document_id", "reason"],
            },
        },
    },    
]

def call_tool(name: str, arguments: dict, session: Session, documents: dict[str, Document]) -> dict:
    handler = TOOLS.get(name)
    if handler is None:
        return {"status": "unknown_tool", "tool": name}
    return handler(session, documents, arguments)


def parse_arguments(raw) -> dict:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    return {}
