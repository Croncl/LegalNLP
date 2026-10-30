"""Busca e resposta sobre o indice do modulo legado (baseline).

Este modulo so ENVOLVE o legado (rag_cgu_pipeline.py, extraido do notebook sem alteracoes).
Conforme o projeto evoluir, a logica migra do legado para modulos proprios.
"""
from __future__ import annotations

from . import config  # noqa: F401  (define RAG_DB e RAG_EMB_MODEL antes do import do legado)
from .llm_local import LLMLocal

PROMPT_SISTEMA = (
    "Voce responde perguntas sobre documentos da CGU usando SOMENTE os trechos fornecidos. "
    "Cite sempre o documento e as paginas entre colchetes, no formato [documento, pags X-Y]. "
    "Se os trechos nao trazem a resposta, diga que nao ha evidencia nos documentos."
)  # prompt inicial; substitua pelo v2 do notebook para comparar com o baseline original


def _legado():
    from .legado import rag_cgu_pipeline as legado
    return legado


def abrir_db():
    return _legado().connect()


def buscar(con, pergunta: str, k: int = 5, denso: bool = True):
    """Devolve lista de (score, linha). Usa FTS5/BM25 + vetores com fusao RRF (legado)."""
    return _legado().search(con, pergunta, k, denso)


def montar_contexto(resultados) -> str:
    blocos = []
    for i, (_, r) in enumerate(resultados, 1):
        doc = r["nota_tecnica"] or r["doc_titulo"]
        blocos.append(
            f"[{i}] {doc} | {r['secao']} {r['titulo']} | pags {r['pag_ini']}-{r['pag_fim']}\n{r['texto']}")
    return "\n\n".join(blocos)


def responder(con, pergunta: str, k: int = 4, llm: LLMLocal | None = None) -> dict:
    llm = llm or LLMLocal()
    res = buscar(con, pergunta, k)
    msgs = [
        {"role": "system", "content": PROMPT_SISTEMA},
        {"role": "user", "content": f"TRECHOS:\n{montar_contexto(res)}\n\nPERGUNTA: {pergunta}"},
    ]
    return {"resposta": llm.chat(msgs, max_tokens=500), "fontes": [
        {"documento": r["nota_tecnica"] or r["doc_titulo"], "pags": (r["pag_ini"], r["pag_fim"]),
         "link": r["link_fonte"]} for _, r in res]}
