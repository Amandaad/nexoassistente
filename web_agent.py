"""Decisões do protótipo web com trilha legível para o funcionário."""
from __future__ import annotations

import re

import tools
from mock_service import TicketService


RE_ID = re.compile(r"INC-\d+", re.I)
SEGURANCA = ("phishing", "invadid", "vazamento", "hackea", "ransomware", "vírus", "virus")
CRITICO = ("todos", "ninguém consegue", "sistema fora", "parou tudo", "fora do ar")


class NexoWebAgent:
    def __init__(self, ticket_service: TicketService):
        self.ticket_service = ticket_service

    @staticmethod
    def _result(
        message: str,
        understood: str,
        action: str,
        confidence: int,
        reason: str,
        *,
        actions: list[str] | None = None,
        ticket: dict | None = None,
        draft: dict | None = None,
        confirmation: dict | None = None,
        quick_replies: list[str] | None = None,
        handoff: bool = False,
    ) -> dict:
        return {
            "message": message,
            "trace": {
                "understood": understood,
                "action": action,
                "confidence": confidence,
                "reason": reason,
                "actions": actions or [],
            },
            "ticket": ticket,
            "draft": draft,
            "confirmation": confirmation,
            "quick_replies": quick_replies or [],
            "handoff": handoff,
        }

    def process(self, text: str, solicitante: str, session: dict) -> dict:
        if session.get("awaiting_human"):
            raise RuntimeError("Esta conversa já foi transferida para um atendente.")

        normalized = text.casefold()
        match = RE_ID.search(text)

        if any(term in normalized for term in SEGURANCA + CRITICO) or (
            "analista" in normalized or "pessoa" in normalized
        ):
            urgent = any(term in normalized for term in SEGURANCA + CRITICO)
            ticket = None
            actions = ["classificou a prioridade", "transferiu a conversa para um analista"]
            if match:
                ticket = self.ticket_service.transfer_ticket(match.group(), solicitante)
            if ticket is None:
                ticket = self.ticket_service.create_ticket(
                    solicitante,
                    "Atendimento humano solicitado",
                    text,
                    "Crítica" if urgent else "Média",
                )
                ticket = self.ticket_service.transfer_ticket(ticket["id"], solicitante)
                actions.insert(0, "registrou o pedido de atendimento")
            session["awaiting_human"] = True
            return self._result(
                "Transferi esta conversa para um analista. O atendimento automático foi pausado.",
                "O funcionário pediu atendimento humano ou descreveu uma situação que exige escalonamento.",
                "Transferir a conversa e aguardar um atendente.",
                96 if urgent else 91,
                "O pedido explícito de uma pessoa, um incidente de segurança ou impacto amplo exige atendimento humano.",
                actions=actions,
                ticket=ticket,
                handoff=True,
            )

        if match and any(term in normalized for term in ("cancel", "cancele")):
            session["pending_confirmation"] = {"type": "cancel", "ticket_id": match.group().upper()}
            ticket = self.ticket_service.get_ticket(match.group(), solicitante)
            if ticket is None:
                session.pop("pending_confirmation", None)
                return self._result(
                    "Não encontrei esse chamado entre os seus chamados.",
                    f"O funcionário pediu para cancelar {match.group().upper()}.",
                    "Não executar a alteração.",
                    99,
                    "O serviço não encontrou um chamado pertencente ao funcionário.",
                    actions=["consultou seus chamados"],
                )
            return self._result(
                f"Confirma o cancelamento do {ticket['id']}?",
                f"O funcionário quer cancelar o chamado {ticket['id']}.",
                "Pedir confirmação antes de cancelar.",
                98,
                "O cancelamento altera o estado do chamado e exige confirmação explícita.",
                actions=["consultou o chamado"],
                ticket=ticket,
                confirmation={"kind": "cancel", "ticket_id": ticket["id"]},
                quick_replies=["Confirmar cancelamento", "Manter chamado"],
            )

        if match and any(term in normalized for term in ("atualiz", "adicion", "comentário", "comentario")):
            ticket = self.ticket_service.update_ticket(match.group(), solicitante, text)
            if ticket is None:
                return self._result(
                    "Não encontrei esse chamado entre os seus chamados.",
                    f"O funcionário tentou atualizar {match.group().upper()}.",
                    "Não executar a alteração.",
                    99,
                    "O serviço não encontrou um chamado pertencente ao funcionário.",
                    actions=["validou a titularidade do chamado"],
                )
            return self._result(
                f"Atualizei o {ticket['id']}. Status atual: {ticket['status']}.",
                f"O funcionário quer adicionar uma atualização ao {ticket['id']}.",
                "Adicionar comentário ao chamado.",
                94,
                "O chamado pertence ao funcionário e aceita atualizações.",
                actions=["validou a titularidade", "adicionou comentário ao chamado"],
                ticket=ticket,
            )

        if match:
            ticket = self.ticket_service.get_ticket(match.group(), solicitante)
            if ticket is None:
                return self._result(
                    "Não encontrei esse chamado entre os seus chamados.",
                    f"O funcionário consultou {match.group().upper()}.",
                    "Não revelar dados do chamado.",
                    99,
                    "O serviço não encontrou um chamado pertencente ao funcionário.",
                    actions=["validou a titularidade do chamado"],
                )
            return self._result(
                f"{ticket['id']} — {ticket['titulo']}: {ticket['status']} (prioridade {ticket['prioridade']}).",
                f"O funcionário quer consultar o status do {ticket['id']}.",
                "Consultar chamado próprio.",
                98,
                "O identificador do chamado foi informado e o serviço validou a titularidade.",
                actions=["consultou o chamado"],
                ticket=ticket,
            )

        if "meus chamados" in normalized or "meu chamado" in normalized or "status" in normalized:
            tickets = self.ticket_service.list_tickets(solicitante)
            message = (
                "Você ainda não tem chamados."
                if not tickets
                else "Aqui estão seus chamados. Selecione um para ver os detalhes."
            )
            return self._result(
                message,
                "O funcionário quer consultar os chamados em seu nome.",
                "Listar chamados próprios.",
                97,
                "A lista foi filtrada pelo usuário da sessão.",
                actions=["consultou seus chamados"],
                ticket={"items": tickets},
            )

        knowledge = tools.buscar_base_conhecimento(text)
        if knowledge["encontrado"]:
            return self._result(
                f"{knowledge['resposta']}\n\nArtigo {knowledge['id']}. Se não resolver, posso abrir um chamado.",
                f"O funcionário fez uma pergunta relacionada a “{knowledge['titulo']}”.",
                "Buscar resposta na central de ajuda.",
                86,
                "A consulta correspondeu a termos cadastrados no artigo da central de ajuda.",
                actions=["consultou a central de ajuda"],
            )

        if len(text.split()) < 4:
            return self._result(
                "Pode me contar um pouco mais? O que acontece e desde quando?",
                "Ainda não há detalhes suficientes para encontrar uma orientação ou registrar o problema.",
                "Solicitar mais contexto.",
                64,
                "A mensagem é curta e não permite identificar o problema com segurança.",
                actions=["avaliou a descrição"],
                quick_replies=["Não consigo acessar", "Meu equipamento parou", "Preciso instalar um programa"],
            )

        draft = {
            "titulo": text[:60].strip(),
            "descricao": text,
            "prioridade": "Média",
        }
        session["pending_confirmation"] = {"type": "create", "draft": draft}
        return self._result(
            "Preparei um rascunho do chamado. Revise e confirme para enviar.",
            "O funcionário descreveu um problema que não foi encontrado na central de ajuda.",
            "Preparar abertura de chamado para confirmação.",
            78,
            "Não há artigo correspondente; a abertura só será feita após confirmação do funcionário.",
            actions=["consultou a central de ajuda", "preparou rascunho de chamado"],
            draft=draft,
            confirmation={"kind": "create"},
            quick_replies=["Confirmar abertura"],
        )

    def confirm(self, solicitante: str, session: dict, confirm: bool) -> dict:
        pending = session.pop("pending_confirmation", None)
        if pending is None:
            raise ValueError("Não há nenhuma confirmação pendente.")
        if not confirm:
            return self._result(
                "Tudo bem — não fiz nenhuma alteração.",
                "O funcionário decidiu não confirmar a ação sugerida.",
                "Descartar a ação pendente.",
                100,
                "A ação não foi executada sem confirmação.",
                actions=["descartou a ação pendente"],
            )
        if pending["type"] == "create":
            draft = pending["draft"]
            ticket = self.ticket_service.create_ticket(
                solicitante, draft["titulo"], draft["descricao"], draft["prioridade"]
            )
            return self._result(
                f"Chamado {ticket['id']} aberto com sucesso.",
                "O funcionário confirmou o rascunho de abertura.",
                "Criar chamado.",
                100,
                "A criação foi executada após confirmação explícita.",
                actions=["criou chamado após confirmação"],
                ticket=ticket,
            )
        ticket = self.ticket_service.update_ticket(
            pending["ticket_id"], solicitante, "Cancelamento confirmado pelo usuário", cancelar=True
        )
        if ticket is None:
            raise ValueError("O chamado não está disponível para este usuário.")
        return self._result(
            f"Chamado {ticket['id']} cancelado.",
            f"O funcionário confirmou o cancelamento de {ticket['id']}.",
            "Cancelar chamado.",
            100,
            "O serviço validou a titularidade e o cancelamento foi confirmado.",
            actions=["cancelou chamado após confirmação"],
            ticket=ticket,
        )
