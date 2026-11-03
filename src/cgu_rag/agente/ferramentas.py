"""Ferramentas do agente (R7): consulta a base de documentos da CGU (RAG)."""
from __future__ import annotations

from langchain_core.tools import tool


def formatar_trechos(linhas, max_car: int = 900) -> str:
    """Texto que o modelo recebe: um bloco por trecho, com documento, secao, paginas, link e o texto."""
    if not linhas:
        return "Nenhum trecho encontrado para essa consulta."
    blocos = []
    for i, r in enumerate(linhas, 1):
        doc = r["nota_tecnica"] or r["doc_titulo"]
        cabecalho = f"[{i}] {doc} | {r['secao'] or ''} {r['titulo'] or ''} | pags {r['pag_ini']}-{r['pag_fim']}"
        if r["link_fonte"]:
            cabecalho += f" | {r['link_fonte']}"
        blocos.append(cabecalho + "\n" + " ".join((r["texto"] or "").split())[:max_car])
    return "\n\n".join(blocos)


def criar_ferramenta_consulta(buscador, k: int = 4, max_car: int = 900):
    """`buscador(consulta, k)` devolve as linhas mais relevantes (ex.: BM25 + vetores com RRF).
    k e max_car limitam o tamanho do resultado para caber no contexto do modelo local."""

    @tool
    def consultar_base(consulta: str) -> str:
        """Busca trechos nos normativos e manuais da CGU sobre PAD e PAR (prazos, ritos, regras e conceitos).
        Use frases curtas com termos tecnicos. Se os trechos nao responderem, reformule e busque de novo."""
        return formatar_trechos(buscador(consulta, k), max_car)

    return consultar_base
