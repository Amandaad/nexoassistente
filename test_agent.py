"""Cenários de teste do Nexo Assist (modo offline). Rode: python test_agent.py"""
import tools
from agent import responder_offline


def novo():
    return {}


def test_duvida_faq():
    r = responder_offline("esqueci minha senha", "ana", novo())
    assert "senha.nexo.corp" in r


def test_consulta_chamado_proprio():
    r = responder_offline("qual o status do INC-1001?", "ana", novo())
    assert "Em andamento" in r and "Carlos" in r


def test_nao_vaza_chamado_de_outro():
    r = responder_offline("status do INC-1002", "ana", novo())
    assert "só pode consultar" in r


def test_listar_meus_chamados():
    r = responder_offline("quais meus chamados?", "ana", novo())
    assert "INC-1001" in r and "INC-1002" not in r


def test_abre_chamado_novo():
    r = responder_offline("o monitor da minha mesa piscou e apagou de vez", "joao", novo())
    assert "Abri o chamado INC-" in r


def test_pede_detalhes_quando_vago():
    r = responder_offline("não funciona", "ana", novo())
    assert "detalhes" in r


def test_atualiza_chamado():
    r = responder_offline("atualize o INC-1002: segue o print do erro", "joao", novo())
    assert "Em andamento" in r


def test_cancelar_exige_confirmacao():
    est = novo()
    r = responder_offline("cancele o INC-1001", "ana", est)
    assert "Confirma" in r and tools.CHAMADOS["INC-1001"]["status"] != "Cancelado"
    r = responder_offline("sim", "ana", est)
    assert "cancelado" in r and tools.CHAMADOS["INC-1001"]["status"] == "Cancelado"


def test_analista_pedido_explicito():
    r = responder_offline("quero falar com um analista", "ana", novo())
    assert "analista" in r.lower()


def test_seguranca_aciona_analista_urgente():
    n = len(tools.FILA_ANALISTAS)
    r = responder_offline("recebi um phishing e cliquei no link", "ana", novo())
    assert len(tools.FILA_ANALISTAS) == n + 1 and tools.FILA_ANALISTAS[-1]["urgente"]


if __name__ == "__main__":
    import copy
    base = copy.deepcopy(tools.CHAMADOS)
    fs = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for f in fs:
        tools.CHAMADOS.clear()
        tools.CHAMADOS.update(copy.deepcopy(base))
        tools.FILA_ANALISTAS.clear()
        f()
        print("ok", f.__name__)
    print(f"{len(fs)} cenários passaram")
