"""Servidor HTTP local para o protótipo web do Nexo Assist."""
from __future__ import annotations

import json
import os
import secrets
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from agent import NexoWebAgent
from mock_service import TicketService


ROOT = Path(__file__).resolve().parent
MAX_MESSAGES = 30
SERVICE = TicketService()
AGENT = NexoWebAgent(SERVICE)
SESSIONS: dict[str, dict] = {}


class NexoHandler(BaseHTTPRequestHandler):
    server_version = "NexoPrototype/1.0"

    def _json(self, status: int, payload: dict, headers: dict[str, str] | None = None) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 16_384:
            raise ValueError("Corpo da solicitação muito grande.")
        data = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(data, dict):
            raise ValueError("O corpo da solicitação deve ser um objeto JSON.")
        return data

    def _session_id(self) -> str | None:
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        morsel = cookie.get("nexo_session")
        return morsel.value if morsel else None

    def _session(self) -> dict | None:
        session_id = self._session_id()
        return SESSIONS.get(session_id) if session_id else None

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/me":
            session = self._session()
            if not session:
                self._json(401, {"error": "Faça login para continuar."})
                return
            self._json(
                200,
                {
                    "usuario": session["usuario"],
                    "mensagens_restantes": MAX_MESSAGES - session["messages_used"],
                    "aguardando_atendente": session["awaiting_human"],
                    "chamados": SERVICE.list_tickets(session["usuario"]),
                },
            )
            return
        if path == "/api/tickets":
            session = self._session()
            if not session:
                self._json(401, {"error": "Faça login para continuar."})
                return
            self._json(200, {"chamados": SERVICE.list_tickets(session["usuario"])})
            return
        asset = "index.html" if path == "/" else path.lstrip("/")
        if asset not in {"index.html", "app.js", "styles.css"}:
            self._json(404, {"error": "Rota não encontrada."})
            return
        target = ROOT / asset
        content_type = "text/html; charset=utf-8" if asset.endswith(".html") else (
            "text/javascript; charset=utf-8" if asset.endswith(".js") else "text/css; charset=utf-8"
        )
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            body = self._body()
            if path == "/api/login":
                username = str(body.get("usuario", "")).strip()
                password = str(body.get("senha", ""))
                if not username or not password:
                    self._json(400, {"error": "Informe usuário e senha."})
                    return
                session_id = secrets.token_urlsafe(24)
                SESSIONS[session_id] = {
                    "usuario": username.casefold(),
                    "messages_used": 0,
                    "awaiting_human": False,
                    "pending_confirmation": None,
                }
                self._json(
                    200,
                    {"usuario": username, "mensagens_restantes": MAX_MESSAGES},
                    {"Set-Cookie": f"nexo_session={session_id}; HttpOnly; SameSite=Lax; Path=/"},
                )
                return

            session = self._session()
            if not session:
                self._json(401, {"error": "Faça login para continuar."})
                return
            if path == "/api/logout":
                session_id = self._session_id()
                if session_id:
                    SESSIONS.pop(session_id, None)
                self._json(
                    200,
                    {"ok": True},
                    {"Set-Cookie": "nexo_session=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0"},
                )
                return
            if path == "/api/new-session":
                session.update({
                    "messages_used": 0,
                    "awaiting_human": False,
                    "pending_confirmation": None,
                })
                self._json(200, {"mensagens_restantes": MAX_MESSAGES})
                return
            if path == "/api/chat":
                text = str(body.get("message", "")).strip()
                if not text:
                    self._json(400, {"error": "A mensagem não pode ficar vazia."})
                    return
                if session["awaiting_human"]:
                    self._json(409, {"error": "Esta conversa aguarda atendimento humano."})
                    return
                if session["messages_used"] + 2 > MAX_MESSAGES:
                    self._json(429, {"error": "Esta sessão atingiu o limite de 30 mensagens."})
                    return
                result = AGENT.process(text, session["usuario"], session)
                session["messages_used"] += 2
                result["mensagens_restantes"] = MAX_MESSAGES - session["messages_used"]
                self._json(200, result)
                return
            if path == "/api/confirm":
                if session["messages_used"] + 2 > MAX_MESSAGES:
                    self._json(429, {"error": "Esta sessão atingiu o limite de 30 mensagens."})
                    return
                result = AGENT.confirm(
                    session["usuario"], session, bool(body.get("confirmar", False))
                )
                session["messages_used"] += 2
                result["mensagens_restantes"] = MAX_MESSAGES - session["messages_used"]
                self._json(200, result)
                return
            self._json(404, {"error": "Rota não encontrada."})
        except (ValueError, json.JSONDecodeError) as error:
            self._json(400, {"error": str(error)})
        except RuntimeError as error:
            self._json(409, {"error": str(error)})

    def log_message(self, format: str, *args: object) -> None:
        print(f"[nexo] {self.address_string()} - {format % args}")


def main() -> None:
    host = "127.0.0.1"
    port = int(os.environ.get("NEXO_PORT", "8000"))
    print(f"Nexo Assist disponível em http://{host}:{port}")
    print(f"Persistência SQLite: {SERVICE.database_path}")
    ThreadingHTTPServer((host, port), NexoHandler).serve_forever()


if __name__ == "__main__":
    main()
