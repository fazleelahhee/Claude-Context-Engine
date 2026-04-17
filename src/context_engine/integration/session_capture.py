"""Session history capture — records decisions, code areas, and Q&A for future recall."""
import json
import time
import uuid
from pathlib import Path

class SessionCapture:
    def __init__(self, sessions_dir: str) -> None:
        self._sessions_dir = sessions_dir
        Path(sessions_dir).mkdir(parents=True, exist_ok=True)
        self._active: dict[str, dict] = {}

    def start_session(self, project_name: str) -> str:
        session_id = uuid.uuid4().hex[:12]
        self._active[session_id] = {
            "id": session_id, "project": project_name, "started_at": time.time(),
            "decisions": [], "code_areas": [], "questions": [],
        }
        return session_id

    def record_decision(self, session_id, decision, reason):
        session = self._active.get(session_id)
        if session:
            session["decisions"].append({"decision": decision, "reason": reason, "timestamp": time.time()})

    def record_code_area(self, session_id, file_path, description):
        session = self._active.get(session_id)
        if session:
            session["code_areas"].append({"file_path": file_path, "description": description, "timestamp": time.time()})

    def record_question(self, session_id, question, answer):
        session = self._active.get(session_id)
        if session:
            session["questions"].append({"question": question, "answer": answer, "timestamp": time.time()})

    def get_decisions(self, session_id):
        session = self._active.get(session_id)
        return session["decisions"] if session else []

    def get_code_areas(self, session_id):
        session = self._active.get(session_id)
        return session["code_areas"] if session else []

    def end_session(self, session_id):
        session = self._active.pop(session_id, None)
        if session:
            session["ended_at"] = time.time()
            file_path = Path(self._sessions_dir) / f"{session_id}.json"
            with open(file_path, "w") as f:
                json.dump(session, f, indent=2)

    def load_recent_sessions(self, limit=5):
        sessions_path = Path(self._sessions_dir)
        files = sorted(sessions_path.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        sessions = []
        for f in files[:limit]:
            with open(f) as fp:
                sessions.append(json.load(fp))
        return sessions
