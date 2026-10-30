"""Metricas de recuperacao (hit@k e MRR) sobre um gabarito em JSONL.

Formato de cada linha do gabarito (ADAPTE ao formato do benchmark do notebook, se diferente):
  {"id": "q01", "pergunta": "...", "esperado": "Nota Tecnica n 1234/2023"}
Um resultado conta como acerto se `esperado` aparece (sem diferenciar maiusculas) no nome da Nota
Tecnica, no titulo do documento ou no titulo da secao do trecho recuperado.
"""
from __future__ import annotations

import json
from pathlib import Path


def acertou(esperado: str, linha) -> bool:
    campos = [linha["nota_tecnica"] or "", linha["doc_titulo"] or "", linha["titulo"] or ""]
    return any(esperado.lower() in c.lower() for c in campos)


def posicao_do_acerto(esperado: str, linhas: list) -> int | None:
    """Posicao (1-based) do primeiro acerto, ou None."""
    for i, linha in enumerate(linhas, 1):
        if acertou(esperado, linha):
            return i
    return None


def metricas(posicoes: list[int | None], k: int) -> dict:
    n = len(posicoes) or 1
    hits = sum(1 for p in posicoes if p is not None and p <= k)
    mrr = sum(1 / p for p in posicoes if p is not None and p <= k) / n
    return {"n": len(posicoes), f"hit@{k}": round(hits / n, 4), f"mrr@{k}": round(mrr, 4)}


def avaliar_recuperacao(gabarito: str | Path, con, k: int = 5, denso: bool = True) -> dict:
    from .busca import buscar
    itens = [json.loads(l) for l in Path(gabarito).read_text(encoding="utf-8").splitlines() if l.strip()]
    posicoes = []
    for it in itens:
        linhas = [r for _, r in buscar(con, it["pergunta"], k, denso)]
        posicoes.append(posicao_do_acerto(it["esperado"], linhas))
    return metricas(posicoes, k)
