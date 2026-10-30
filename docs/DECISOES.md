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
- **Status:** A validar
- **Decisão:** `ollama pull hf.co/mauroneto/Jurema-7B-Q4_K_M-GGUF`.
- **Alternativa:** quantizar o original `Jurema-br/Jurema-7B` com llama.cpp (exige ~16 GB livres e mais etapas).
- **Motivo:** menor esforço e mesmo modelo-base (ajuste do Qwen2.5-7B-Instruct para direito brasileiro).
- **Riscos:** a conversão **não é oficial** e o conteúdo do repositório não foi auditado. O modelo original exige aceite de termos e é destinado a pesquisa e desenvolvimento.
- **Mitigação:** citar modelo e autor da conversão no README; registrar que o uso é acadêmico; comparar com `qwen2.5:3b`.
- **Confirmação do autor:** ______ (data)

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

## D-08 Metodologia de avaliação da recuperação
- **Status:** A validar
- **Decisão:** gabarito **sintético** de 30 perguntas (LLM local escreve a pergunta a partir de uma seção sorteada, semente 42); acerto **estrito** (mesmo documento, mesma seção, páginas sobrepostas); métricas hit@1/3/5/10 e MRR@10; cada medição gravada em `results/progresso.json`.
- **Limite:** perguntas sintéticas favorecem a busca lexical; revisar manualmente e, se possível, usar o benchmark original.
- **Alternativa:** gabarito 100% manual (mais confiável, mais trabalhoso).
- **Confirmação do autor:** ______ (data)

## D-09 Domínio e corpus
- **Status:** A validar (com a dupla)
- **Decisão:** correição e processo administrativo disciplinar; 6 PDFs públicos da Base de Conhecimento da CGU (links em `src/cgu_rag/fontes.py`, a criar).
- **Motivo:** corpus real e público, já ingerido (1567 trechos), com o baseline pronto.
- **Confirmação da dupla:** ______ (data)

## D-10 Política de sigilo com falha fechada
- **Status:** Aceita
- **Decisão:** com `SIGILO=sigiloso`, só endpoint local ou de rede privada; sem fallback para provedor externo.
- **Motivo:** o domínio é administrativo e pode envolver dados sensíveis; o corpus atual é público, mas a política evita vazamento por engano.
