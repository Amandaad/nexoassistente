"""Serviço simulado de chamados, isolado do agente e persistido em SQLite."""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


class TicketService:
    def __init__(self, database_path: str | os.PathLike[str] | None = None):
        self.database_path = Path(
            database_path or os.environ.get("NEXO_DB_PATH", "nexo.sqlite3")
        )
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @staticmethod
    def _ticket(row: sqlite3.Row) -> dict:
        ticket = dict(row)
        ticket["historico"] = ticket["historico"].split("\n") if ticket["historico"] else []
        return ticket

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS tickets (
                    id TEXT PRIMARY KEY,
                    solicitante TEXT NOT NULL,
                    titulo TEXT NOT NULL,
                    descricao TEXT NOT NULL,
                    status TEXT NOT NULL,
                    prioridade TEXT NOT NULL,
                    analista TEXT,
                    historico TEXT NOT NULL
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS ticket_sequence (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    next_value INTEGER NOT NULL
                )"""
            )
            connection.execute(
                "INSERT OR IGNORE INTO ticket_sequence (id, next_value) VALUES (1, 1003)"
            )
            count = connection.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
            if count == 0:
                connection.executemany(
                    """INSERT INTO tickets
                    (id, solicitante, titulo, descricao, status, prioridade, analista, historico)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    [
                        (
                            "INC-1001", "ana", "Notebook não liga",
                            "Notebook corporativo não liga desde o início da manhã.",
                            "Em andamento", "Alta", "Carlos",
                            "Aberto\nAtribuído a Carlos",
                        ),
                        (
                            "INC-1002", "joao", "Acesso ao sistema financeiro",
                            "Solicitação de acesso ao sistema financeiro.",
                            "Aguardando usuário", "Média", "Marina",
                            "Aberto\nMarina pediu print do erro",
                        ),
                    ],
                )

    def list_tickets(self, solicitante: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM tickets WHERE solicitante = ? ORDER BY id DESC",
                (solicitante,),
            ).fetchall()
        return [self._ticket(row) for row in rows]

    def get_ticket(self, id_chamado: str, solicitante: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM tickets WHERE id = ? AND solicitante = ?",
                (id_chamado.upper(), solicitante),
            ).fetchone()
        return self._ticket(row) if row else None

    def create_ticket(
        self,
        solicitante: str,
        titulo: str,
        descricao: str,
        prioridade: str = "Média",
    ) -> dict:
        prioridades = {"Baixa", "Média", "Alta", "Crítica"}
        if prioridade not in prioridades:
            raise ValueError(f"Prioridade inválida: {prioridade}")
        with self._connect() as connection:
            next_value = connection.execute(
                "SELECT next_value FROM ticket_sequence WHERE id = 1"
            ).fetchone()[0]
            connection.execute(
                "UPDATE ticket_sequence SET next_value = ? WHERE id = 1",
                (next_value + 1,),
            )
            ticket_id = f"INC-{next_value}"
            history = f"Aberto em {datetime.now(timezone.utc).astimezone():%d/%m %H:%M}"
            connection.execute(
                """INSERT INTO tickets
                (id, solicitante, titulo, descricao, status, prioridade, analista, historico)
                VALUES (?, ?, ?, ?, 'Aberto', ?, NULL, ?)""",
                (ticket_id, solicitante, titulo, descricao, prioridade, history),
            )
        ticket = self.get_ticket(ticket_id, solicitante)
        if ticket is None:
            raise RuntimeError("O chamado foi criado, mas não pôde ser recuperado.")
        return ticket

    def update_ticket(
        self,
        id_chamado: str,
        solicitante: str,
        comentario: str,
        cancelar: bool = False,
    ) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM tickets WHERE id = ? AND solicitante = ?",
                (id_chamado.upper(), solicitante),
            ).fetchone()
            if row is None:
                return None
            ticket = self._ticket(row)
            if ticket["status"] in ("Resolvido", "Cancelado"):
                raise ValueError(f"Chamado já está {ticket['status']}.")
            history = ticket["historico"] + [f"Usuário: {comentario}"]
            status = "Cancelado" if cancelar else ticket["status"]
            if not cancelar and status == "Aguardando usuário":
                status = "Em andamento"
            connection.execute(
                "UPDATE tickets SET historico = ?, status = ? WHERE id = ?",
                ("\n".join(history), status, ticket["id"]),
            )
        return self.get_ticket(ticket["id"], solicitante)

    def transfer_ticket(self, id_chamado: str, solicitante: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM tickets WHERE id = ? AND solicitante = ?",
                (id_chamado.upper(), solicitante),
            ).fetchone()
            if row is None:
                return None
            ticket = self._ticket(row)
            history = ticket["historico"] + ["Transferido para atendimento humano"]
            connection.execute(
                "UPDATE tickets SET status = ?, historico = ? WHERE id = ?",
                ("Aguardando atendente", "\n".join(history), ticket["id"]),
            )
        return self.get_ticket(ticket["id"], solicitante)
