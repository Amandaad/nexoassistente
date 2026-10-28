"""Nexo Assist: agent de atendimento do service desk de TI.

Dois modos:
  - Claude (padrão, requer ANTHROPIC_API_KEY): o modelo decide qual ferramenta usar.
  - Offline (--offline): roteador por regras, para testes sem rede.
"""
from __future__ import annotations
import argparse
import json
import os
import re

import tools
from web_agent import NexoWebAgent

MODELO = os.environ.get("NEXO_MODEL", "claude-sonnet-5-5")

SYSTEM = """Você é o Nexo Assist, agent de atendimento do service desk de TI da Nexo Corp (empresa fictícia).
Fale em português do Brasil, de forma curta, cordial e objetiva.

Decida a cada mensagem entre:
1. Dúvida comum -> use buscar_base_conhecimento e responda com o artigo. Se não resolver, ofereça abrir chamado.
2. Consultar chamado -> consultar_chamado (com ID) ou listar_meus_chamados (sem ID).
3. Atualizar chamado -> atualizar_chamado. Para CANCELAR, peça confirmação explícita antes.
4. Problema novo que a base não resolve -> abrir_chamado. Se faltar informação essencial, pergunte antes (no máximo uma pergunta).
5. Chamar analista -> chamar_analista quando: o usuário pedir uma pessoa; houver incidente de segurança (phishing, vazamento, conta invadida); ou impacto crítico (sistema parado para várias pessoas).

Regras:
- Nunca invente status de chamado ou artigos; use apenas o que as ferramentas retornarem.
- Nunca revele dados de chamados de outras pessoas.
- Não peça senhas ou dados sensíveis ao usuário.
- Ao abrir chamado ou acionar analista, informe o ID/posição retornado.
"""


# ---------- Modo Claude ----------
def executar_ferramenta(nome: str, args: dict, usuario: str) -> dict:
    fn = tools.FUNCOES.get(nome)
    if not fn:
        return {"erro": f"Ferramenta desconhecida: {nome}"}
    if nome != "buscar_base_conhecimento":
        args = {**args, "solicitante": usuario}
    try:
        return fn(**args)
    except TypeError as e:
        return {"erro": f"Argumentos inválidos: {e}"}


def responder_claude(historico: list, usuario: str, client) -> str:
    # 'solicitante' não está nos schemas: é injetado pelo sistema, não pelo modelo
    for _ in range(8):
        r = client.messages.create(model=MODELO, max_tokens=1024, system=SYSTEM,
                                   tools=tools.SCHEMAS, messages=historico)
        historico.append({"role": "assistant", "content": r.content})
        if r.stop_reason != "tool_use":
            return "".join(b.text for b in r.content if b.type == "text")
        resultados = []
        for b in r.content:
            if b.type == "tool_use":
                out = executar_ferramenta(b.name, b.input, usuario)
                resultados.append({"type": "tool_result", "tool_use_id": b.id,
                                   "content": json.dumps(out, ensure_ascii=False)})
        historico.append({"role": "user", "content": resultados})
    return "Não consegui concluir agora. Vou chamar um analista para ajudar."


# ---------- Modo offline (regras) ----------
RE_ID = re.compile(r"INC-\d+", re.I)
SEGURANCA = ["phishing", "invadid", "vazamento", "hackea", "ransomware", "vírus", "virus"]
CRITICO = ["todos", "ninguém consegue", "sistema fora", "parou tudo", "fora do ar"]


def responder_offline(texto: str, usuario: str, estado: dict) -> str:
    t = texto.lower()
    m = RE_ID.search(texto)

    # confirmação de cancelamento pendente
    if estado.get("cancelar_pendente"):
        id_ = estado.pop("cancelar_pendente")
        if t.strip() in ("sim", "s", "confirmo", "pode cancelar"):
            r = tools.atualizar_chamado(id_, usuario, "Cancelado pelo usuário", cancelar=True)
            return f"Chamado {r['id']} cancelado." if "id" in r else r["erro"]
        return "Ok, mantive o chamado como está."

    if "analista" in t or "pessoa" in t or any(k in t for k in SEGURANCA) or any(k in t for k in CRITICO):
        urgente = any(k in t for k in SEGURANCA + CRITICO)
        r = tools.chamar_analista(usuario, texto, urgente)
        return r["mensagem"] + f" (posição {r['posicao_na_fila']} na fila)"

    if m and "cancel" in t:
        estado["cancelar_pendente"] = m.group(0).upper()
        return f"Confirma o cancelamento do {m.group(0).upper()}? Responda 'sim' para confirmar."

    if m and ("atualiz" in t or "adicion" in t or "comentário" in t):
        r = tools.atualizar_chamado(m.group(0), usuario, texto)
        return f"Chamado {r['id']} atualizado (status: {r['status']})." if "id" in r else r["erro"]

    if m:
        c = tools.consultar_chamado(m.group(0), usuario)
        if "erro" in c:
            return c["erro"]
        return f"{c['id']} - {c['titulo']}: {c['status']} (prioridade {c['prioridade']}, analista: {c['analista'] or 'a definir'})."

    if "meus chamados" in t or "meu chamado" in t or "status" in t:
        lst = tools.listar_meus_chamados(usuario)["chamados"]
        if not lst:
            return "Você não tem chamados abertos."
        return "Seus chamados:\n" + "\n".join(f"- {c['id']}: {c['titulo']} ({c['status']})" for c in lst)

    kb = tools.buscar_base_conhecimento(texto)
    if kb["encontrado"]:
        return f"{kb['resposta']}\n(Artigo {kb['id']}). Se não resolver, posso abrir um chamado."

    if len(texto.split()) < 4:
        return "Pode me dar mais detalhes do problema (o que acontece, desde quando)?"
    r = tools.abrir_chamado(usuario, texto[:60], texto)
    return f"Abri o chamado {r['id']} (prioridade {r['prioridade']}). Um analista vai acompanhar."


# ---------- CLI ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--usuario", default="ana")
    a = ap.parse_args()

    client = None
    if not a.offline:
        import anthropic
        client = anthropic.Anthropic()

    print("Nexo Assist - digite 'sair' para encerrar.")
    historico, estado = [], {}
    while True:
        try:
            msg = input("Você: ").strip()
        except EOFError:
            break
        if msg.lower() in ("sair", "exit"):
            break
        if not msg:
            continue
        if a.offline:
            print("Nexo:", responder_offline(msg, a.usuario, estado))
        else:
            historico.append({"role": "user", "content": msg})
            print("Nexo:", responder_claude(historico, a.usuario, client))


if __name__ == "__main__":
    main()
