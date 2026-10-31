# Diário de execução (erros, causas e correções)

Uma linha por ocorrência. Formato: data | etapa | ocorrência | causa | correção.

| Data | Etapa | Ocorrência | Causa | Correção |
|---|---|---|---|---|
| 29/10 | 3 Ingestão | `NameError: FONTES` | Célula de configuração antiga ainda no kernel | Célula única com config, FONTES, download e ingestão |
| 29/10 | 3 Ingestão | 6 PDFs baixados e ingeridos | , | Pasta `data/pdfs/` é cache: não baixa de novo |
| 29/10 | 6 Embeddings | 1567 trechos em 362 s (`multilingual-e5-small`) | , | Baseline registrado |
| 30/10 | 9 Resposta | `APIConnectionError` | Ollama não instalado | `winget install Ollama.Ollama` (v0.40.13) |
| 30/10 | LLM | `qwen2.5:3b` respondeu "pronto" | , | Servidor validado (D-02) |
| 30/10 | LLM | Jurema-7B Q4_K_M baixado (4,7 GB) e apelido `jurema-7b` | , | D-04 e D-05 |
| 30/10 | 8 LLM | Jurema: 1º token em 0,13 s e ~11,8 blocos/s (prompt curto) | , | Medição com contexto de RAG fica na etapa 8b |
| 30/10 | 9 Resposta | `NameError: responder` e `con` | Kernel reiniciado; variáveis perdidas | Célula 1b "Retomada" no notebook |
| 30/10 | 10 Avaliação | hit@k = 0 com 1 pergunta | Gabarito era só o texto-modelo | Gabarito sintético de 30 perguntas (D-08) |
| 30/10 | Notebook | Notebook anterior gravava saídas com caminho local do Windows | , | Saídas limpas antes de commitar |
| 30/10 | Decisoes | D-04 confirmada; D-08 (gabarito com validacao humana) e D-09 (dominio por fases) registradas | , | Documentos atualizados pelo script R1b |
| 30/10 | R2 | Ingestao movida do notebook para src/cgu_rag/ingestao.py e scripts/ingerir.py | , | Mesmo comportamento; data/pdfs/ funciona como cache |
| 30/10 | R2c | Repositorio com .vscode e Untitled.ipynb versionados; gabarito sintetico e notebook com saidas modificados | , | Itens removidos do Git; gabarito movido para rascunho.jsonl; saidas do notebook limpas |
| 30/10 | R3a | Revisao humana do gabarito (D-08) com campo fase (D-11) | , | Criados src/cgu_rag/gabarito.py, scripts/gabarito.py e tests/test_gabarito.py |
| 30/10 | R3a | Campo fase virou multisselecao + fora_do_fluxo | As tres fases nao cobrem todas as perguntas | D-11 revisada (opcao A); modulo, tela e testes ajustados |
| 30/10 | R3a | Campo fase virou multisselecao + fora_do_fluxo | As tres fases nao cobrem todas as perguntas | D-11 revisada (opcao A); modulo, tela e testes ajustados |
| 30/10 | R3a | Corpus tem documentos de PAR (outro rito); revisao do gabarito zerada | Fases do PAD nao se aplicam ao PAR | Categoria exclusiva par (D-11) e D-09 ampliada; backup em ~/rascunho_revisado_backup.jsonl |
| 30/10 | R3b | Metricas e graficos movidos para src/cgu_rag/metricas.py e scripts/avaliar.py | , | matplotlib adicionado ao pyproject; resultados em results/progresso.json e results/*.png |
| 30/10 | R3b | Metricas e graficos movidos para src/cgu_rag/metricas.py e scripts/avaliar.py | , | matplotlib adicionado ao pyproject; resultados em results/progresso.json e results/*.png |
| 30/10 | R3b | pyproject.toml invalido apos Set-Content -Encoding UTF8; matplotlib nao entrou na lista de dependencias | PowerShell 5.1 grava BOM e o TOML nao aceita | Regravado sem BOM (WriteAllText); dependencia adicionada; usar gravacao sem BOM em TOML e JSON |
