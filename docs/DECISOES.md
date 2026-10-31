# Registro de Decisões (ADR simplificado)

Projeto: assistente agêntico sobre normativos da CGU (correição e processo disciplinar).
Disciplina: IA Agêntica, Avaliação da Unidade II. Dupla: *(preencher os dois nomes)*.

**Como usar:** uma decisão por bloco. Status possíveis: `Aceita`, `A validar`, `Substituída`.
Decisões `A validar` só viram `Aceita` depois da confirmação explícita do autor (anotar a data).

---

## D-01 Servidor de LLM local: Ollama
- **Status:** Aceita
- **Contexto:** o agente precisa de um LLM local (corpus tratado com política de sigilo).
- **Decisão:** usar o Ollama (API compatível com OpenAI em `http://localhost:11434/v1`).
- **Alternativas:** llama.cpp (`llama-server`), LM Studio, vLLM (foca em GPU/Linux, não serve para CPU no Windows).
- **Motivo:** o gargalo é o modelo de 7B na CPU, não o servidor; o Ollama é simples de instalar e reproduzir. Trocar depois exige só mudar `LLM_BASE_URL`.
- **Revisão:** comparar com `llama-server` somente se a latência medida for ruim.

## D-02 Validar o servidor com um modelo pequeno antes do Jurema
- **Status:** Aceita (executada: `qwen2.5:3b` respondeu "pronto")
- **Motivo:** separar falhas de servidor de falhas de modelo; o 3B também serve como modelo menor de comparação.

## D-03 Passar o modelo por parâmetro (`LLMLocal(model=...)`)
- **Status:** Substituída
- **Motivo original:** testar o 3B sem reiniciar o kernel.
- **Substituída por:** o modelo vem da variável `LLM_MODEL` (padrão `jurema-7b`); o notebook usa `LLMLocal()`.

## D-04 Jurema-7B via GGUF Q4_K_M comunitário
- **Status:** Aceita (confirmada pelo autor em 30/10/2026)
- **Decisão:** `ollama pull hf.co/mauroneto/Jurema-7B-Q4_K_M-GGUF`.
- **Alternativa:** quantizar o original `Jurema-br/Jurema-7B` com llama.cpp (exige ~16 GB livres e mais etapas).
- **Motivo:** menor esforço e mesmo modelo-base (ajuste do Qwen2.5-7B-Instruct para direito brasileiro).
- **Riscos:** a conversão **não é oficial** e o conteúdo do repositório não foi auditado. O modelo original exige aceite de termos e é destinado a pesquisa e desenvolvimento.
- **Mitigação:** citar modelo e autor da conversão no README; registrar que o uso é acadêmico; comparar com `qwen2.5:3b`.
- **Confirmação do autor:** 30/10/2026

## D-05 Apelido `jurema-7b` via `ollama cp`
- **Status:** Aceita
- **Motivo:** o código usa `jurema-7b` como nome padrão; o apelido não duplica os 4,7 GB. Parâmetros (`num_ctx`, threads) só depois de medir.

## D-06 Modelo de embeddings: baseline e5-small; testar bge-m3
- **Status:** A validar (depende do experimento A3)
- **Contexto:** `intfloat/multilingual-e5-small` corta em 512 tokens; os trechos têm mediana de ~1600 caracteres.
- **Decisão proposta:** manter o e5-small como baseline (A1/A2) e testar `BAAI/bge-m3` (até 8192 tokens) em um banco separado (`data/rag_cgu_bgem3.db`).
- **Alternativas:** e5-base, encoders jurídicos em português (janela curta).
- **Critério:** escolher pelo hit@k e MRR do mesmo gabarito, considerando tempo de indexação.
- **Confirmação do autor:** ______ (data)

## D-07 Projeto modular em Python; notebook só para experimentos
- **Status:** Aceita
- **Motivo:** Streamlit executa arquivos `.py`; LangGraph, servidores MCP e testes exigem código importável; o README precisa ser reproduzível.
- **Estrutura:** `src/cgu_rag/` (núcleo), `src/cgu_rag/agente/` (grafo), `mcp_servers/`, `skills/`, `app/`, `scripts/`, `notebooks/`, `tests/`, `docs/`.

## D-08 Metodologia de avaliacao da recuperacao (gabarito com validacao humana)
- **Status:** Aceita (decisao do autor em 30/10/2026; substitui a versao com gabarito sintetico automatico)
- **Decisao:** o gabarito tem **validacao manual**. Fluxo:
  1. O sistema gera um **rascunho** de perguntas candidatas (LLM local, a partir de secoes sorteadas, semente 42) em `data/gabarito/rascunho.jsonl`, todas com `status: pendente`.
  2. O autor revisa cada item: **aprova**, **edita a pergunta** ou **descarta**.
  3. Somente itens `aprovado` entram em `data/gabarito/perguntas.jsonl`, com o campo `fase` (admissibilidade, acusatoria ou julgamento; ver D-11).
- **Metricas:** hit@1/3/5/10 e MRR@10; acerto **estrito** (mesmo documento, mesma secao, paginas sobrepostas); cada medicao em `results/progresso.json`.
- **Motivo:** a revisao humana torna o processo mais confiavel e reduz o vies de perguntas sinteticas, que repetem termos do trecho e favorecem a busca lexical.
- **Custo:** mais trabalho manual; meta minima de 30 perguntas aprovadas.
- **Implementacao:** passo R3.

## D-09 Dominio: processo disciplinar (PAD) e de responsabilizacao (PAR) da CGU
- **Status:** Aceita pelo autor em 30/10/2026 (ampliada com o PAR); **a confirmar com a dupla**
- **Decisao:** o assistente cobre dois processos distintos:
  1. **PAD (processo disciplinar)**, em tres fases:
     - **Admissibilidade:** busca elementos minimos de materialidade e autoria para instaurar o PAD. Em regra nao ha contraditorio. Pode ser uma investigacao preliminar sumaria (IPS) ou apenas o juizo de admissibilidade. Principio: *in dubio pro societate*.
     - **Acusatoria (PAD / sindicancia acusatoria, comissao constituida):** o "acusado" (termo da lei) e chamado ao processo e pode se manifestar. Principio: *in dubio pro reu*.
     - **Julgamento / parecer opinativo:** apos a conclusao do PAD, com relatorio final da comissao e recomendacao (arquivamento ou penalidade).
  2. **PAR (Processo Administrativo de Responsabilizacao):** apura a responsabilidade objetiva de pessoas juridicas por atos lesivos contra a administracao publica nacional ou estrangeira (Lei 12.846/2013; no ambito federal, regulamentado pelo Decreto 11.129/2022, segundo a descricao do autor). Rito proprio: apuracao preliminar quando necessaria (IP ou IPS), instauracao por portaria com comissao processante, citacao e instrucao com contraditorio e ampla defesa, relatorio final e julgamento. Entre as sancoes: multa de 0,1% a 20% do faturamento bruto e publicacao extraordinaria da decisao; programas de integridade pesam na dosimetria.
  - O PAR e tratado como categoria **separada** do PAD e nao usa as fases do PAD.
  - **TAC (Termo de Ajustamento de Conduta):** encaminhamento possivel, como o arquivamento, conforme normativo tipico da CGU. Nao e fase.
- **Corpus:** 6 PDFs publicos da Base de Conhecimento da CGU (1567 trechos ja ingeridos).
- **Motivo:** o corpus contem documentos de PAD e de PAR, que seguem ritos diferentes.
- **Pendente (nao decidido):** como usar a separacao no sistema (skills, guardrails, filtro de busca).
- **Confirmacao da dupla:** ______ (data)

## D-10 Política de sigilo com falha fechada
- **Status:** Aceita
- **Decisão:** com `SIGILO=sigiloso`, só endpoint local ou de rede privada; sem fallback para provedor externo.
- **Motivo:** o domínio é administrativo e pode envolver dados sensíveis; o corpus atual é público, mas a política evita vazamento por engano.

## D-12 Estrutura do repositorio
- **Status:** Aceita (confirmada pelo autor em 30/10/2026)
- **Decisao:** uma pasta por responsabilidade: `src/cgu_rag/` (nucleo e, depois, `agente/`), `mcp_servers/`, `skills/`, `app/`, `scripts/`, `notebooks/`, `tests/`, `docs/`, `data/` e `results/`. Scripts de configuracao ficam na raiz.
- **Fora do Git:** `.env`, bancos `.db`, PDFs, `.vscode/`, modelos e saidas de notebook.
- **Motivo:** o codigo que o Streamlit chama fica so em `src/`; nada local ou sigiloso vai para o repositorio publico.
- **Confirmacao do autor:** 30/10/2026

## D-11 Campo `fase` no gabarito (multisselecao, com PAR)
- **Status:** Aceita (autor, 30/10/2026: opcao A, ampliada com a categoria PAR)
- **Decisao:** cada pergunta aprovada tem `fase`, obrigatoria, com um destes formatos:
  - lista com uma ou mais fases do PAD: `admissibilidade`, `acusatoria`, `julgamento` (as tres juntas = transversal; nao existe valor `geral`);
  - `par` (valor exclusivo): pergunta sobre o processo de responsabilizacao;
  - `fora_do_fluxo` (valor exclusivo): pergunta que nao e etapa de processo (ex.: efeitos da penalidade, como o impedimento apos a demissao).
- **Teclas na revisao:** `1`, `2`, `3` (combinaveis, ex.: `13`), `4` = PAR, `0` = fora do fluxo.
- **TAC nao e fase:** e um possivel encaminhamento; a pergunta recebe as fases em que se aplica.
- **Metricas:** pergunta de varias fases conta em cada uma; `par` e `fora_do_fluxo` aparecem separados.
- **Limite:** pergunta valida para PAD e PAR ao mesmo tempo nao tem categoria propria.
- **Skills:** nao mudam; serao definidas no R10 por tarefa de varias etapas.
- **Alternativas descartadas:** tres fases unicas (B) e dois campos, fase e tema (C). Campo `processo` separado (para PAD e PAR) fica como evolucao possivel.

## D-13 Prioridade: agente antes de otimizar a recuperacao
- **Status:** Aceita (autor, 30/10/2026, opcao 1)
- **Decisao:** seguir para o agente (R6 em diante); o notebook fino (R4) e o experimento com bge-m3 (R5) ficam adiados.
- **Motivo:** os requisitos da Unidade II sao do agente; o baseline ja e bom (hit@5 = 0.93, hit@10 = 0.97).
- **Risco:** a ordenacao fraca (hit@1 = 0.5) pode afetar as respostas; a rebusca do RAG agentico (R7) deve mitigar e o R5 pode ser retomado.

## D-14 Grafo: estado simples, LLM via LLMLocal e checkpointer em memoria
- **Status:** A validar
- **Decisao:** estado com `messages` (lista de dicts, reducer de soma), `bloqueado`, `ferramentas` e `skills` (os dois ultimos para a interface exibir por resposta). LLM injetado (`LLMLocal`), sem LangChain. Checkpointer `MemorySaver`, uma thread por conversa. Ao LLM vai so o historico recente (10 mensagens); o estado guarda tudo.
- **Motivo:** grafo proprio, como o requisito pede; estado transparente e serializavel; preserva a politica de sigilo (D-10); testes sem Ollama; o contexto do modelo local e limitado (num_ctx 4096).
- **Alternativas:** `create_agent` ou `langchain-openai` (menos controle sobre os nos); `SqliteSaver` (persiste entre execucoes; avaliar se a interface exigir).
- **Em aberto:** como o modelo decide consultar a base (tool calling nativo ou JSON estruturado). A testar no R7: o GGUF comunitario do Jurema pode nao suportar tool calling.
- **Confirmacao do autor:** ______ (data)
