"""Testes do agente web e do serviço simulado persistente."""
import tempfile
import unittest
from pathlib import Path

from agent import NexoWebAgent
from mock_service import TicketService


class NexoWebAgentTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.service = TicketService(Path(self.temp_dir.name) / "tickets.sqlite3")
        self.agent = NexoWebAgent(self.service)
        self.session = {"awaiting_human": False, "pending_confirmation": None}

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_resposta_da_central_exibe_decisao(self):
        result = self.agent.process("Esqueci minha senha", "ana", self.session)
        self.assertIn("senha.nexo.corp", result["message"])
        self.assertEqual(result["trace"]["action"], "Buscar resposta na central de ajuda.")
        self.assertIn("consultou a central de ajuda", result["trace"]["actions"])

    def test_chamado_so_e_criado_apos_confirmacao(self):
        result = self.agent.process(
            "Meu monitor parou de funcionar e preciso de ajuda desde esta manhã.",
            "ana",
            self.session,
        )
        self.assertIsNotNone(result["draft"])
        self.assertEqual(len(self.service.list_tickets("ana")), 1)

        created = self.agent.confirm("ana", self.session, True)
        self.assertEqual(created["ticket"]["id"], "INC-1003")
        self.assertEqual(len(self.service.list_tickets("ana")), 2)

    def test_nao_expoe_chamado_de_outro_usuario(self):
        result = self.agent.process("status do INC-1002", "ana", self.session)
        self.assertIsNone(result["ticket"])
        self.assertIn("Não encontrei", result["message"])

    def test_transferencia_pausa_o_agente_e_persiste_chamado(self):
        result = self.agent.process("Quero falar com um analista", "ana", self.session)
        self.assertTrue(result["handoff"])
        self.assertEqual(result["ticket"]["status"], "Aguardando atendente")
        self.assertTrue(self.session["awaiting_human"])
        with self.assertRaises(RuntimeError):
            self.agent.process("Mais uma dúvida", "ana", self.session)

    def test_chamados_sobrevivem_a_reinicializacao_do_servico(self):
        self.service.create_ticket("ana", "Teste de persistência", "Descrição de teste")
        reopened = TicketService(self.service.database_path)
        self.assertTrue(
            any(ticket["titulo"] == "Teste de persistência" for ticket in reopened.list_tickets("ana"))
        )


if __name__ == "__main__":
    unittest.main()
