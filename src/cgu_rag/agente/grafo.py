"""Grafo LangGraph do assistente (passo R6): estado, nos, arestas e memoria por conversa.

Fluxo:  entrada -> (bloqueado? saida : responder) -> saida
- entrada:   normaliza o turno e zera ferramentas/skills usadas (ponto onde entrara o guardrail de entrada, R11)
- responder: chama o LLM com o historico recente (aqui entrara o RAG agentico, R7)
- saida:     entrega a resposta ou a recusa (ponto do guardrail de saida, R11)
Memoria: checkpointer por thread_id (uma conversa = uma thread).
"""
from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

PROMPT_SISTEMA = (
    "Voce e um assistente sobre processos de correição da CGU: processo administrativo disciplinar (PAD) "
    "e processo administrativo de responsabilizacao (PAR). Responda em portugues, de forma objetiva. "
    "Se nao souber, diga que nao sabe."
)
MAX_MSGS = 10  # mensagens recentes enviadas ao LLM (o contexto do modelo local e limitado)


class Estado(TypedDict, total=False):
    messages: Annotated[list[dict], operator.add]  # historico da conversa (soma a cada turno)
    bloqueado: str        # motivo da recusa; vazio se liberado
    ferramentas: list     # ferramentas chamadas neste turno (a interface exibe)
    skills: list          # skills carregadas neste turno (a interface exibe)


def criar_grafo(llm, max_msgs: int = MAX_MSGS, checkpointer=None):
    """`llm` e qualquer objeto com chat(mensagens) -> str (ex.: LLMLocal)."""

    def entrada(estado: Estado) -> dict:
        vazio = not estado["messages"][-1]["content"].strip()
        return {"bloqueado": "mensagem vazia" if vazio else "", "ferramentas": [], "skills": []}

    def responder(estado: Estado) -> dict:
        recentes = [m for m in estado["messages"] if m["content"].strip()][-max_msgs:]
        texto = llm.chat([{"role": "system", "content": PROMPT_SISTEMA}] + recentes)
        return {"messages": [{"role": "assistant", "content": texto.strip()}]}

    def saida(estado: Estado) -> dict:
        if estado.get("bloqueado"):
            return {"messages": [{"role": "assistant", "content": f"Nao posso processar: {estado['bloqueado']}."}]}
        return {}

    def rota(estado: Estado) -> str:
        return "saida" if estado.get("bloqueado") else "responder"

    g = StateGraph(Estado)
    g.add_node("entrada", entrada)
    g.add_node("responder", responder)
    g.add_node("saida", saida)
    g.add_edge(START, "entrada")
    g.add_conditional_edges("entrada", rota, {"responder": "responder", "saida": "saida"})
    g.add_edge("responder", "saida")
    g.add_edge("saida", END)
    return g.compile(checkpointer=checkpointer or MemorySaver())


def conversar(grafo, texto: str, thread_id: str) -> tuple[str, dict]:
    """Um turno. Devolve (resposta, estado final). O thread_id identifica a conversa."""
    cfg = {"configurable": {"thread_id": thread_id}}
    out = grafo.invoke({"messages": [{"role": "user", "content": texto}]}, cfg)
    return out["messages"][-1]["content"], out
