# cgu-rag: baseline modular do RAG CGU com LLM local

Esqueleto para o trabalho acadêmico. A lógica vive em `src/cgu_rag/`; os notebooks só chamam o pacote.
O módulo `legado/rag_cgu_pipeline.py` é o módulo de apoio do notebook *RAG CGU Completo*, extraído **sem
alterações** (ingestão, limpeza, seções, SQLite com BM25, vetores e RRF). Ele é o seu **baseline**.

```
src/cgu_rag/
  config.py       variáveis de ambiente (.env), define RAG_DB e RAG_EMB_MODEL antes do legado
  llm_local.py    cliente OpenAI-compatível (Ollama/llama.cpp) com política de sigilo (falha fechada)
  busca.py        busca e resposta sobre o índice do legado
  avaliacao.py    hit@k e MRR sobre um gabarito .jsonl
  legado/         rag_cgu_pipeline.py (não editar; migrar por partes para módulos próprios)
scripts/medir_llm.py   mede tempo até o 1º token e velocidade do modelo
notebooks/01_fluxo_completo.ipynb
tests/test_smoke.py
```

## Passo a passo (máquina Ryzen 7, 48 GB)

1. **Ambiente** (Python 3.10+):
   ```
   python -m venv .venv
   # Linux/macOS: source .venv/bin/activate     Windows: .venv\Scripts\activate
   pip install -e ".[dev,notebook]"
   cp .env.example .env
   pytest        # deve passar (9 testes)
   ```
2. **Dados:** coloque os PDFs em `data/pdfs/` (corpus público da CGU) e **não** os versione.
3. **Acesso ao Jurema-7B:** entre com sua conta no Hugging Face, abra `Jurema-br/Jurema-7B` e aceite os
   termos. Para rodar na CPU use uma versão **quantizada (GGUF)** de origem conferida, ou quantize você
   mesmo com llama.cpp a partir do original (precisa de ~16 GB livres).
4. **Servidor do LLM** (Ollama, por exemplo). Importe o GGUF com um `Modelfile`:
   ```
   FROM ./models/jurema-7b-q4_k_m.gguf
   PARAMETER num_ctx 4096
   PARAMETER num_thread 8        # ajuste para o número de núcleos FÍSICOS
   ```
   ```
   ollama create jurema-7b -f Modelfile
   ollama run jurema-7b "Diga olá."
   ```
   O Ollama expõe a API em `http://localhost:11434/v1` (já é o padrão do `.env`).
5. **Medir a velocidade** (guarde cada configuração testada):
   ```
   python scripts/medir_llm.py
   ```
   Se o tempo até o primeiro token passar de ~1 minuto com 3000 tokens, reduza `num_ctx`, use menos trechos
   (k) ou teste um modelo menor.
6. **Baseline:** abra `notebooks/01_fluxo_completo.ipynb` (Jupyter ou VS Code) e rode do início ao fim. Ele cria o banco SQLite, ingere os PDFs, limpa, enriquece, gera embeddings, busca, responde com o LLM local e avalia; nenhuma etapa depende do Colab. Depois crie
   `data/gabarito/perguntas.jsonl` com o benchmark do notebook original e confirme que hit@k e MRR batem
   com os valores que você já tinha. **Só então** mude alguma coisa.

## Ordem de evolução (ver seções 8 e 18 do documento técnico)
1. Reproduzir o baseline. 2. Trazer do LegalNLP: regex de metadados, revogação/vigência e citação por página.
3. Ampliar o benchmark (>30 perguntas) e medir BM25, RRF, embeddings e reranker um de cada vez.
4. Comparar geração: Jurema-7B contra modelo menor (JSON válido, fidelidade de citação, recusa sem evidência).
5. Opcional: título inferido e Laya (com ajuste fino).

## Observações
- O `llm_local.py` só aceita endpoint local ou de rede privada quando `SIGILO=sigiloso`. Para usar uma API externa
  (por exemplo, como juiz da avaliação com dados públicos), use `SIGILO=publico` e um modelo **diferente** do gerador.
- O módulo legado usa provedores externos de LLM só no enriquecimento por LLM (`--enrich llm`); o enriquecimento
  `heuristic` não precisa de LLM.
- O prompt de `busca.py` é inicial. Para comparar com o baseline original, use o prompt v2 do notebook.
