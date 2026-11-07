# Resumo para iniciar um novo chat: LegalNLP / RAG CGU (Unidade II, IA Agêntica)

Atualizado em 07/11/2026. Cole este arquivo no início do novo chat. Repositório: https://github.com/Croncl/LegalNLP (branch main). Pasta local: `C:\Users\k12_crslcrn\Documents\Projetos\cgu_rag_projeto`. Windows, PowerShell 5.1, ambiente conda `cgu-rag` (Python 3.11), Ollama 0.40.15. PC principal: Ryzen 7, 48 GB de RAM, sem GPU relevante (inferência em CPU); notebook secundário com RTX 4050.

## 1. O trabalho
Avaliação da Unidade II (IA Agêntica), em dupla (preencher os nomes no README). Construir um assistente em **grafo LangGraph** (estado, nós e arestas próprios) com interface **Streamlit**, contendo:
1. RAG agêntico sobre documentos reais (o modelo decide quando consultar, reformula e busca de novo; informar a origem dos documentos).
2. MCP: pelo menos 1 servidor desenvolvido pela dupla (ferramentas próprias) e 1 da comunidade.
3. Pelo menos 2 skills em `SKILL.md`, carregadas sob demanda a partir de um catálogo na mensagem de sistema (cada skill ensina uma tarefa de várias etapas do domínio).
4. Memória com checkpointer (uma thread por conversa).
5. Guardrails de entrada e saída como nós do grafo, contra pelo menos 2 riscos concretos do domínio.
6. Streamlit: chat, nova conversa, exibição das ferramentas chamadas e das skills carregadas em cada resposta.
Entrega: link do repositório e vídeo de até 5 minutos. O README é o relatório: título e nomes, o que o assistente faz e para quem, diagrama do grafo com a função de cada nó, componentes e decisões, **10 casos de teste** (entrada, esperado, obtido, aprovado; pelo menos 3 desafiadores; cobrindo RAG, 2 skills, 2 servidores MCP, memória e guardrails), taxa de acerto e análise dos erros. Deve rodar só com o README; chaves de API em variáveis de ambiente.

**Domínio:** processo disciplinar da CGU. PAD em 3 fases (admissibilidade, acusatória, julgamento/parecer) e PAR (processo de responsabilização de pessoas jurídicas, Lei 12.846/2013) como categoria separada. TAC é um possível encaminhamento (como o arquivamento), não uma fase. Corpus: 6 PDFs públicos da Base de Conhecimento da CGU (1567 trechos). Detalhes na D-09.

## 2. Como o usuário quer ser atendido
- **Um passo de cada vez**, com teste e confirmação ("R7 ok") antes do próximo; saídas curtas; explicar sempre o motivo das escolhas e das alterações.
- Mudanças por **comandos de terminal (PowerShell)** que alteram os arquivos diretamente, dizendo exatamente o que e onde muda. Um comando por bloco (já houve erro por colagem de duas linhas juntas).
- Arquivos longos: entregar para download e dar o `Copy-Item "$HOME\Downloads\arquivo" destino\` (o navegador renomeia repetidos, ex.: `chat (1).py`).
- **Documentar tudo**: `docs/DECISOES.md` (decisões, com status e confirmação), `docs/DIARIO.md` (erros e correções), `docs/ROTEIRO.md`, `docs/RESULTADOS.md`, `docs/MODELOS.md`. Decisões importantes precisam da validação dele.
- Armadilhas do ambiente: `Set-Content -Encoding UTF8` grava BOM no PowerShell 5.1 (ok em .py e .md; **quebra TOML e JSON**: use `[System.IO.File]::WriteAllText(..., (New-Object System.Text.UTF8Encoding($false)))`). Avisos de CRLF do Git são inofensivos. O `git push` já falhou uma vez por falta de rede.

## 3. Estado do repositório
```
src/cgu_rag/  config, fontes, ingestao, llm_local, busca, avaliacao, gabarito, metricas
              legado/rag_cgu_pipeline.py (baseline do notebook original, nao editar)
              agente/  modelo.py (ChatOpenAI no Ollama com politica de sigilo), grafo.py, ferramentas.py
scripts/      ingerir, gabarito (revisar/status/exportar), avaliar, chat, depurar, testar_tools, medir_agente, medir_llm
tests/        45 testes passando (gabarito, grafo, ferramentas, ingestao, metricas, modelo, smoke)
docs/         DECISOES, DIARIO, ROTEIRO, RESULTADOS, MODELOS, img/
data/gabarito rascunho.jsonl (30 perguntas revisadas a mao), perguntas.jsonl (aprovadas, com campo fase)
models/       Modelfile.jurema-7b (obsoleto; Jurema removido)
notebooks/    01_fluxo_completo.ipynb (saidas limpas; fase experimental)
```
Dependências em `pyproject.toml`: pymupdf, numpy, requests, sentence-transformers, openai, langchain-openai, langgraph, matplotlib. Conferir com `git status` se scripts e tests do R7 já foram commitados (último commit conhecido: `fa984a7`; o commit "R7h" pode estar pendente). `results/` fica fora do Git.

## 4. Grafo atual (R6 a R7)
`entrada -> (bloqueado? saida : responder) ; responder -> (chamou ferramenta? ferramentas -> responder : saida)`.
- Estado: `messages` (mensagens do LangChain, `add_messages`), `bloqueado`, `ferramentas`, `skills`.
- Checkpointer `MemorySaver`, thread por conversa. Ao modelo vai o histórico recente (10 mensagens); nos turnos anteriores só pergunta e resposta final (sem resultados de consulta); limite de 3 consultas por turno.
- Ferramenta `consultar_base` (BM25 + vetores com RRF; 4 trechos de até 900 caracteres, com documento, seção, páginas e link). `criar_buscador()` abre uma conexão SQLite **por thread** (o ToolNode roda em outra thread; esse foi um defeito encontrado e corrigido). `ToolNode(handle_tool_errors=True)`.
- Controle do raciocínio: `LLM_PENSAR=false` envia `reasoning_effort="none"` e `think=false` (**não verificado** que o Ollama o aceite).
- `scripts/depurar.py "pergunta" [--modelo X]` mostra o passo a passo de um turno; `scripts/medir_agente.py --modelo X --n 8` mede o agente no gabarito.

## 5. Roteiro
| Passo | Situação |
|---|---|
| R1, R1b docs e decisões; R2 ingestão em módulo; R2c limpeza do repositório | concluídos |
| R3a revisão humana do gabarito (campo `fase`), R3b métricas e gráficos, R3c baseline oficial | concluídos |
| R4 notebook fino, R5 experimento com bge-m3 | adiados (D-13) |
| R6/R6b grafo com memória e peças do LangChain | concluídos |
| R7 RAG agêntico | implementado; **falta escolher o modelo** (D-17) |
| R8 servidor MCP próprio; R9 servidor MCP da comunidade | pendentes |
| R10 duas skills; R11 guardrails; R12 Streamlit; R13 10 casos de teste, README e vídeo | pendentes |

Ideia registrada para o R11: **guardrail de grounding**: se a resposta cita fonte ou afirma norma sem ter havido consulta, o grafo força a consulta (e as fontes são anexadas pelo sistema a partir dos trechos recuperados, não escritas pelo modelo). Para o R8 foi cogitado um servidor MCP próprio com ferramentas de domínio (por exemplo, cálculo de prazos de prescrição); a escolha das ferramentas deve ser validada com o usuário.

## 6. Decisões (detalhes em docs/DECISOES.md)
D-01 Ollama como servidor local. D-02 validar com modelo pequeno. D-03 substituída. **D-04 Jurema-7B: substituída** (não usa ferramentas; removido). D-05 apelido do modelo (obsoleta). D-06 embeddings: baseline `multilingual-e5-small` (bge-m3 adiado). D-07 projeto modular em Python. D-08 gabarito com validação humana (30 perguntas). D-09 domínio PAD + PAR. D-10 sigilo com falha fechada. D-11 campo `fase` (lista de admissibilidade/acusatoria/julgamento, ou `par`, ou `fora_do_fluxo`). D-12 estrutura do repositório (aceita). D-13 agente antes de otimizar a recuperação. D-14 grafo próprio com peças do LangChain. D-15 RAG agêntico (a validar). D-16 contexto fixado em 8192 (a validar). **D-17 escolha do modelo principal (em andamento).**
Pendentes de confirmação do usuário: D-15, D-16, D-17 (critérios), nomes da dupla, confirmação da D-09 com a dupla.

## 7. Resultados até agora
**Recuperação (30 perguntas revisadas, acerto estrito):** A1 BM25: hit@1 0,500, hit@3 0,833, hit@5 0,867, hit@10 0,967, MRR@10 0,674, 0,009 s. A2 BM25+vetores (RRF): 0,500 / 0,900 / 0,933 / 0,967, MRR 0,695, 0,412 s. Por grupo (hit@5 A1 -> A2): admissibilidade 0,889 -> 1,0; acusatória 0,818 -> 0,909; julgamento 0,875 -> 1,0; par 0,833 -> 1,0; fora_do_fluxo 0,875 -> 0,875. Leitura: recall bom, ordenação fraca (hit@1 0,5).

**Agente (medir_agente.py, n=8, provisório):**
| Modelo | Consultou | Acerto | Consultas/pergunta | s/pergunta |
|---|---|---|---|---|
| Qwen2.5 3B | 75% | 75% | 0,75 | 20,2 |
| Spark-X2.6-4B Q8_0 | 100% | 100% | 1,00 | 158,8 (provável raciocínio ligado) |
| Qwen3.8 27B Q4_K_M | 100% | 100% | 1,38 | 247,6 |
| Qwen2.5 7B | inválido (modelo não estava instalado; 0,3 s era erro) | | | |
| Jurema-7B | 0% | 0% | 0 | 79,8 (inventou leis e artigos sem consultar) |
Limites: n=8 (intervalos de confiança se sobrepõem); "acerto" mede se a consulta trouxe a seção esperada, **não** a qualidade da resposta; só perguntas normativas (não testa saudação nem rebusca em caso difícil). Observação de campo: com `qwen2.5:3b` as respostas se apoiaram nos trechos, mas não houve reformulação/rebusca quando o primeiro trecho não bastava.

## 8. Modelos (Ollama 0.40.15; contexto 8192 via `OLLAMA_CONTEXT_LENGTH`; `OLLAMA_MAX_LOADED_MODELS=1`)
Instalados em 07/11/2026: `qwen2.5:3b`, `qwen2.5:7b` (+ `-instruct-q5_K_M`, `-instruct-q8_0`), `qwen2.5:14b` (Q4_K_M, 9 GB), `qwen3.8:27b-q4_k_m` (17 GB; mesmo ID do antigo `qwen3.8:27b`), `SparkLLM/Spark-X2.6-4B:q8_0` (oficial, 4,4 GB, tools+thinking, contexto máx. 1.048.576), `spark-x2.6-4b:q4_k_m` (3,5 GB, **criado por Modelfile a partir de GGUF local em `C:\Modelos\OllamaGGUF`; procedência a registrar**), `hf.co/nvidia/NVIDIA-Nemotron-3.5-Bolt-E4B-4GB:Q4_K_M` (oficial NVIDIA, 6,2 GB).
Modelo padrão provisório (`config.py`): `SparkLLM/Spark-X2.6-4B:q8_0`. Removidos e justificados em `docs/MODELOS.md`: Jurema (0% de consulta), Spark BF16, aliases. Descartados: AWQ e FP8 (formatos de GPU, não rodam no Ollama em CPU), quantização manual do 27B (já é Q4_K_M; o llama.cpp local build 4400 não reconhece a arquitetura `qwen35`; não existe "Qwen2.5 27B").
Em `C:\Modelos`: pasta `Nemotron` (pesos originais em BF16, 16 GB, download em andamento em 07/11/2026; NAO apagar: servem para quantizações próprias do Nemotron se ele for finalista), `Modelfile`, `Modelfile-Q4`, `Modelfile-Q5` (da tentativa de quantizar o 27B), `MAPA_LOCAL_MODELOS.md` (desatualizado). Manter `OllamaGGUF\spark-x2.6-4b-q4_k_m.gguf` e `Modelfile-Spark` como registro até a procedência ser anotada.

## 9. Plano de escolha do modelo (D-17)
Princípios: mudar uma variável por vez; um modelo carregado por vez; critérios escritos antes de ver resultados; só modelos oficiais (nada "abliterated"); registrar tag, digest, quantização, contexto, raciocínio ligado/desligado e commit.
**Critérios propostos (o usuário ainda não disse "critérios ok"):** eliminatórios: consulta em pelo menos 90% de 30 perguntas normativas; no máximo 1 saudação consultada em 4; zero citação de página sem consulta; no máximo 1 erro por rodada; mediana até 60 s por pergunta. Desempate: qualidade da resposta (rubrica manual de 3 itens: correta e fiel aos trechos, cita a fonte certa, admite falta de evidência), acerto na consulta, latência, memória. O 27B é só referência e, depois, juiz offline.
**Fases:** 0 congelar ambiente (feito); 1 script de medição v2 (aquecimento antes de cronometrar, mediana, respostas completas, perguntas de controle de saudação e fora de escopo, erros contados); 2 triagem com `testar_tools.py`; 3 medição principal n=30 nos aprovados; 4 qualidade das respostas com rubrica; 5 efeito do contexto maior (k=4 contra k=8); 6 decisão D-17 e integração. Etapa B (depois de escolher): comparar quantizações (Q4/Q5/Q8) só dos 2 ou 3 vencedores, com tags oficiais (ex.: `qwen2.5:7b-instruct-q5_K_M`, `-q8_0`; para o 14B provavelmente `qwen2.5:14b-instruct-q5_K_M` e `-q8_0`; o Nemotron oficial só tem Q4_K_M).
O usuário decidiu: estes serão os últimos testes de modelo; escolher 2 ou 3 e seguir às próximas fases.

## 10. Próximo passo imediato
**Triagem** (um modelo por vez; salva em `results\triagem_modelos.txt`):
```powershell
$modelos = @("qwen2.5:3b", "qwen2.5:7b", "qwen2.5:14b", "SparkLLM/Spark-X2.6-4B:q8_0", "spark-x2.6-4b:q4_k_m", "hf.co/nvidia/NVIDIA-Nemotron-3.5-Bolt-E4B-4GB:Q4_K_M")
& {
  foreach ($m in $modelos) {
    $pensa = ($m -match "Spark|spark|Nemotron")
    foreach ($p in $(if ($pensa) { "true", "false" } else { "padrao" })) {
      if ($p -eq "padrao") { Remove-Item Env:LLM_PENSAR -ErrorAction SilentlyContinue } else { $env:LLM_PENSAR = $p }
      "=== $m (LLM_PENSAR=$p)"
      python scripts\testar_tools.py --modelo $m
    }
  }
  Remove-Item Env:LLM_PENSAR -ErrorAction SilentlyContinue
} | Tee-Object -FilePath results\triagem_modelos.txt
```
Ler a **segunda linha** de cada modelo (a primeira inclui a carga): chamou na 1ª pergunta e não na 2ª? tokens baixos com o raciocínio desligado? tempo (alerta acima de 60 s)? erros? Depois: entregar o **script de medição v2** (fase 1), medir n=30 nos aprovados, avaliar qualidade com rubrica, decidir D-17 e seguir para R8 em diante.

