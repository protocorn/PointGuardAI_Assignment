"""Load synthetic employees and documents from data/."""
from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
DATA_DIR = Path(__file__).resolve().parents[1] / "data"


@dataclass(frozen=True)
class Employee:
    id: str
    name: str
    title: str
    department: str
    role: str
    role_label: str
    can_read: tuple[str, ...]


@dataclass(frozen=True)
class Document:
    id: str
    title: str
    clearance: str
    summary: str
    body: str


def load_employees(path: Path = DATA_DIR / "employees.json") -> list[Employee]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    labels = {role["id"]: role["label"] for role in payload["roles"]}
    employees: list[Employee] = []
    for record in payload["employees"]:
        role = record["role"]
        employees.append(
            Employee(
                id=record["id"],
                name=record["name"],
                title=record["title"],
                department=record["department"],
                role=role,
                role_label=labels.get(role, role),
                can_read=tuple(record["can_read"]),
            )
        )
    return employees

def load_documents(directory: Path = DATA_DIR / "documents") -> dict[str, Document]:
    documents: dict[str, Document] = {}
    for path in sorted(directory.glob("DOC-*.md")):
        document = _parse_document(path)
        documents[document.id] = document
    return documents

def _parse_document(path: Path) -> Document:
    lines = path.read_text(encoding="utf-8").splitlines()
    doc_id = ""
    title = ""
    clearance = ""
    summary = ""
    body_start = len(lines)
    for index, line in enumerate(lines):
        if index == 0 and line.startswith("# "):
            title = line.removeprefix("# ").strip()
        elif line.startswith("- Document ID:"):
            doc_id = line.split(":", 1)[1].strip()
        elif line.startswith("- Clearance:"):
            clearance = line.split(":", 1)[1].strip()
        elif line.startswith("- Summary:"):
            summary = line.split(":", 1)[1].strip()
        elif line.strip() == "" and doc_id and clearance and summary and title:
            body_start = index + 1
            break
    body = "\n".join(lines[body_start:]).strip()
    return Document(
        id=doc_id,
        title=title,
        clearance=clearance,
        summary=summary,
        body=body,
    )