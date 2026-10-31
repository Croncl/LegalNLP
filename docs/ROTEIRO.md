# Roteiro de implantação

**Regra de trabalho:** um passo por vez. Cada passo tem: comando de terminal que altera os arquivos, teste de aceite, commit e registro no diário. Decisões marcadas `A validar` precisam de confirmação do autor antes de seguir.

| # | Passo | Teste de aceite | Status |
|---|---|---|---|
| R1 | Documentação base (`docs/`) | Três arquivos existem e abrem | concluído |
| R2 | Módulo de ingestão: `fontes.py` e `scripts/ingerir.py` | `python scripts/ingerir.py` termina sem erro e reconhece os 6 PDFs | concluído |
| R3 | Módulo de métricas e gráficos (`metricas.py`, `scripts/avaliar.py`) e gabarito com revisão humana (`scripts/gabarito.py`) | Gera `results/progresso.json` e os PNG | concluído |
| R4 | Notebook fino (só chama os módulos) | Roda do início ao fim sem erro | adiado (D-13) |
| R5 | Experimento A3 de embeddings (D-06) | hit@k e MRR de A1, A2 e A3 no gráfico | adiado (D-13) |
| R6 | Grafo LangGraph mínimo com checkpointer | Duas perguntas na mesma thread, a segunda usa a primeira | em andamento |
| R7 | RAG agêntico (decide consultar, reformula, rebusca; informa a fonte) | Pergunta vaga é reformulada e rebuscada | pendente |
| R8 | Servidor MCP próprio (`mcp_servers/`) | Ferramentas listadas e chamadas pelo grafo | pendente |
| R9 | Servidor MCP da comunidade | Ferramenta chamada pelo grafo | pendente |
| R10 | Duas skills (`skills/*/SKILL.md`) com catálogo no prompt | Skill carregada sob demanda e exibida | pendente |
| R11 | Guardrails de entrada e saída (nós) | Injeção e pedido fora do escopo bloqueados | pendente |
| R12 | Interface Streamlit | Chat, nova conversa, ferramentas e skills por resposta | pendente |
| R13 | 10 casos de teste, README-relatório e vídeo de 5 min | Tabela entrada, esperado, obtido, aprovado | pendente |

## Boas práticas adotadas
- Chaves de API só em variáveis de ambiente; `.env` fora do repositório.
- Um commit por passo, com mensagem clara; saídas de notebook limpas.
- Cada medição vira linha em `results/progresso.json`.
- Toda decisão relevante entra em `DECISOES.md`; todo erro entra em `DIARIO.md`.




