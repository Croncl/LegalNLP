"""Ferramentas do agente (R7): consulta a base de documentos da CGU (RAG)."""
from __future__ import annotations

import threading

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


def _abrir_db_padrao():
    from ..busca import abrir_db
    return abrir_db()


def _buscar_padrao(con, consulta, k, denso):
    from ..busca import buscar
    return buscar(con, consulta, k, denso)


def criar_buscador(denso: bool = True, abrir=None, buscar_fn=None):
    """Buscador seguro para threads (BM25 + vetores com RRF, via modulo legado).

    O LangGraph executa as ferramentas em threads de trabalho, e uma conexao SQLite so pode ser usada na
    thread que a criou. Por isso cada thread abre a propria conexao na primeira consulta.
    `abrir` e `buscar_fn` existem para os testes; por padrao usam cgu_rag.busca."""
    local = threading.local()

    def buscador(consulta: str, k: int):
        if not hasattr(local, "con"):
            local.con = (abrir or _abrir_db_padrao)()
        return [r for _, r in (buscar_fn or _buscar_padrao)(local.con, consulta, k, denso)]

    return buscador
