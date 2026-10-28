# Nexo Assist

Agent de atendimento do service desk de TI da Nexo Corp (empresa fictícia). O funcionário descreve o problema no chat e o agent decide entre responder uma dúvida, consultar/atualizar chamado, abrir chamado novo ou chamar um analista.

## Como rodar

O protótipo web usa apenas a biblioteca padrão do Python e não precisa instalar dependências:

```bash
python web_server.py
```

Abra `http://127.0.0.1:8000`. No login de demonstração, informe um usuário (por exemplo,
`ana`) e qualquer senha não vazia. O serviço de chamados persiste em `nexo.sqlite3`;
configure `NEXO_DB_PATH` para escolher outro caminho.

```bash
pip install anthropic
export ANTHROPIC_API_KEY=...
python agent.py --usuario ana          # modo Claude
python agent.py --offline --usuario ana  # modo por regras, sem rede
python test_agent.py                   # cenários de teste (offline)
python -m unittest                    # testes automatizados
```

## Arquitetura

- `tools.py`: seis ferramentas com dados simulados (base de conhecimento, chamados, fila de analistas) e seus schemas.
- `agent.py`: loop do agent. O Claude escolhe a ferramenta; o sistema injeta o `solicitante` (usuário logado) em toda chamada, então o modelo nunca decide de quem é o chamado.
- `web_server.py`: API HTTP e servidor local para a interface.
- `web_agent.py`: decisões do chat web e trilha de explicabilidade exibida acima de cada resposta.
- `mock_service.py`: serviço simulado de chamados, isolado do agente e persistido em SQLite.
- `index.html`, `styles.css`, `app.js`: interface responsiva com login demonstrativo, chat, cards, confirmações e transferência para atendente.

## Decisões de design

| Situação | Ação |
|---|---|
| Dúvida comum | `buscar_base_conhecimento` e responde; oferece chamado se não resolver |
| "Status do INC-X" / "meus chamados" | `consultar_chamado` / `listar_meus_chamados` |
| Comentário ou cancelamento | `atualizar_chamado` (cancelar só após confirmação) |
| Problema novo sem solução na base | `abrir_chamado` (pergunta antes se estiver vago) |
| Pedido de pessoa, segurança, impacto crítico | `chamar_analista` (urgente quando aplicável) |

Guardrails: só acessa chamados do próprio usuário, não inventa status, não pede senha.

## Próximos passos

O protótipo web utiliza deliberadamente um serviço de chamados simulado, conforme o escopo do desafio. A conexão a ServiceNow/Jira Service Management e a busca semântica real devem substituir os adaptadores simulados quando houver credenciais, contrato de integração e provedor de embeddings definidos. O SQLite local persiste os chamados desta demonstração; autenticação e histórico de conversa não são persistidos.
