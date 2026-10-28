"""Ferramentas do Nexo Assist (dados simulados em memória)."""
from __future__ import annotations
import itertools
from datetime import datetime

KB = [
    {"id": "KB-001", "titulo": "Redefinir senha da rede",
     "palavras": ["senha", "esqueci", "redefinir", "resetar", "login"],
     "resposta": "Acesse senha.nexo.corp, informe seu e-mail corporativo e siga o código enviado ao celular cadastrado. A nova senha vale após 5 minutos."},
    {"id": "KB-002", "titulo": "Conectar à VPN",
     "palavras": ["vpn", "remoto", "home office", "conectar"],
     "resposta": "Abra o NexoVPN, entre com seu usuário e confirme o MFA. Se falhar, reinstale o cliente pelo Portal de Software."},
    {"id": "KB-003", "titulo": "Impressora não imprime",
     "palavras": ["impressora", "imprimir", "impressão", "fila"],
     "resposta": "Verifique se a impressora está online, limpe a fila de impressão e reinstale o driver pelo Portal de Software."},
    {"id": "KB-004", "titulo": "Wi-Fi corporativo",
     "palavras": ["wifi", "wi-fi", "internet", "rede sem fio"],
     "resposta": "Conecte-se à rede NEXO-CORP com seu usuário e senha de rede. Para visitantes use NEXO-GUEST."},
    {"id": "KB-005", "titulo": "Instalar software",
     "palavras": ["instalar", "software", "programa", "aplicativo"],
     "resposta": "Use o Portal de Software (menu Iniciar). Programas fora do catálogo exigem aprovação do gestor via chamado."},
]

CHAMADOS: dict[str, dict] = {
    "INC-1001": {"id": "INC-1001", "solicitante": "ana", "titulo": "Notebook não liga",
                 "status": "Em andamento", "prioridade": "Alta", "analista": "Carlos",
                 "historico": ["Aberto", "Atribuído a Carlos"]},
    "INC-1002": {"id": "INC-1002", "solicitante": "joao", "titulo": "Acesso ao sistema financeiro",
                 "status": "Aguardando usuário", "prioridade": "Média", "analista": "Marina",
                 "historico": ["Aberto", "Marina pediu print do erro"]},
}
_seq = itertools.count(1003)
FILA_ANALISTAS: list[dict] = []

PRIORIDADES = {"Baixa", "Média", "Alta", "Crítica"}


def buscar_base_conhecimento(consulta: str) -> dict:
    q = consulta.lower()
    pontos = []
    for a in KB:
        p = sum(1 for w in a["palavras"] if w in q)
        if p:
            pontos.append((p, a))
    pontos.sort(key=lambda x: -x[0])
    if not pontos:
        return {"encontrado": False}
    a = pontos[0][1]
    return {"encontrado": True, "id": a["id"], "titulo": a["titulo"], "resposta": a["resposta"]}


def consultar_chamado(id_chamado: str, solicitante: str) -> dict:
    c = CHAMADOS.get(id_chamado.upper())
    if not c:
        return {"erro": f"Chamado {id_chamado} não encontrado."}
    if c["solicitante"] != solicitante:
        return {"erro": "Você só pode consultar chamados abertos por você."}
    return c


def listar_meus_chamados(solicitante: str) -> dict:
    return {"chamados": [c for c in CHAMADOS.values() if c["solicitante"] == solicitante]}


def abrir_chamado(solicitante: str, titulo: str, descricao: str, prioridade: str = "Média") -> dict:
    if prioridade not in PRIORIDADES:
        return {"erro": f"Prioridade inválida. Use: {sorted(PRIORIDADES)}"}
    id_ = f"INC-{next(_seq)}"
    CHAMADOS[id_] = {"id": id_, "solicitante": solicitante, "titulo": titulo,
                     "descricao": descricao, "status": "Aberto", "prioridade": prioridade,
                     "analista": None, "historico": [f"Aberto em {datetime.now():%d/%m %H:%M}"]}
    return {"id": id_, "status": "Aberto", "prioridade": prioridade}


def atualizar_chamado(id_chamado: str, solicitante: str, comentario: str,
                      cancelar: bool = False) -> dict:
    c = CHAMADOS.get(id_chamado.upper())
    if not c or c["solicitante"] != solicitante:
        return {"erro": "Chamado não encontrado para este usuário."}
    if c["status"] in ("Resolvido", "Cancelado"):
        return {"erro": f"Chamado já está {c['status']}."}
    c["historico"].append(f"Usuário: {comentario}")
    if cancelar:
        c["status"] = "Cancelado"
    elif c["status"] == "Aguardando usuário":
        c["status"] = "Em andamento"
    return {"id": c["id"], "status": c["status"]}


def chamar_analista(solicitante: str, motivo: str, urgente: bool = False) -> dict:
    FILA_ANALISTAS.append({"solicitante": solicitante, "motivo": motivo, "urgente": urgente})
    return {"posicao_na_fila": len(FILA_ANALISTAS),
            "mensagem": "Um analista foi acionado e entrará em contato em breve."
                        if not urgente else "Analista acionado com urgência."}


FUNCOES = {
    "buscar_base_conhecimento": buscar_base_conhecimento,
    "consultar_chamado": consultar_chamado,
    "listar_meus_chamados": listar_meus_chamados,
    "abrir_chamado": abrir_chamado,
    "atualizar_chamado": atualizar_chamado,
    "chamar_analista": chamar_analista,
}

_s = {"type": "string"}
SCHEMAS = [
    {"name": "buscar_base_conhecimento", "description": "Busca artigo na base de conhecimento para responder dúvidas comuns de TI.",
     "input_schema": {"type": "object", "properties": {"consulta": _s}, "required": ["consulta"]}},
    {"name": "consultar_chamado", "description": "Consulta status e histórico de um chamado do usuário pelo ID (ex.: INC-1001).",
     "input_schema": {"type": "object", "properties": {"id_chamado": _s}, "required": ["id_chamado"]}},
    {"name": "listar_meus_chamados", "description": "Lista os chamados do usuário quando ele não informa o ID.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "abrir_chamado", "description": "Abre chamado novo. Use só depois de a base de conhecimento não resolver. Peça detalhes se a descrição for vaga.",
     "input_schema": {"type": "object", "properties": {
         "titulo": _s, "descricao": _s,
         "prioridade": {"type": "string", "enum": ["Baixa", "Média", "Alta", "Crítica"]}},
         "required": ["titulo", "descricao"]}},
    {"name": "atualizar_chamado", "description": "Adiciona comentário ou cancela um chamado do usuário. Cancelar exige confirmação explícita do usuário antes.",
     "input_schema": {"type": "object", "properties": {
         "id_chamado": _s, "comentario": _s, "cancelar": {"type": "boolean"}},
         "required": ["id_chamado", "comentario"]}},
    {"name": "chamar_analista", "description": "Aciona analista humano: incidente crítico, segurança, pedido explícito do usuário ou quando o agent não consegue resolver.",
     "input_schema": {"type": "object", "properties": {"motivo": _s, "urgente": {"type": "boolean"}},
                      "required": ["motivo"]}},
]
