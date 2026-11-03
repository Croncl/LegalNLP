"""Grafo LangGraph do assistente: estado, nos, arestas e memoria por conversa (D-14).

Fluxo:  entrada -> (bloqueado? saida : responder) -> saida
- entrada:   normaliza o turno e zera ferramentas/skills usadas (ponto do guardrail de entrada, R11)
- responder: chama o modelo com o historico recente (aqui entrara o RAG agentico, R7)
- saida:     entrega a resposta ou a recusa (ponto do guardrail de saida, R11)
Memoria: checkpointer por thread_id (uma conversa = uma thread).
"""
from __future__ import annotations

from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

PROMPT_SISTEMA = (
    "Voce e um assistente sobre processos de correicao da CGU: processo administrativo disciplinar (PAD) "
    "e processo administrativo de responsabilizacao (PAR). Responda em portugues, de forma objetiva. "
    "Se nao souber, diga que nao sabe."
)
MAX_MSGS = 10  # mensagens recentes enviadas ao modelo (o contexto do modelo local e limitado)


class Estado(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]  # historico da conversa
    bloqueado: str        # motivo da recusa; vazio se liberado
    ferramentas: list     # ferramentas chamadas neste turno (a interface exibe)
    skills: list          # skills carregadas neste turno (a interface exibe)


def _humana_vazia(m) -> bool:
    return isinstance(m, HumanMessage) and not str(m.content).strip()


def recentes(mensagens: list, max_msgs: int) -> list:
    """Ultimas mensagens sem mensagens vazias do usuario, comecando sempre por uma mensagem do usuario
    (um corte no meio de uma chamada de ferramenta deixaria resposta de ferramenta sem a chamada)."""
    sel = [m for m in mensagens if not _humana_vazia(m)][-max_msgs:]
    while sel and not isinstance(sel[0], HumanMessage):
        sel.pop(0)
    return sel


def criar_grafo(modelo, max_msgs: int = MAX_MSGS, checkpointer=None):
    """`modelo` e qualquer objeto com invoke(mensagens) -> AIMessage (ex.: criar_modelo())."""

    def entrada(estado: Estado) -> dict:
        vazio = _humana_vazia(estado["messages"][-1])
        return {"bloqueado": "mensagem vazia" if vazio else "", "ferramentas": [], "skills": []}

    def responder(estado: Estado) -> dict:
        resposta = modelo.invoke([SystemMessage(PROMPT_SISTEMA)] + recentes(estado["messages"], max_msgs))
        return {"messages": [resposta]}

    def saida(estado: Estado) -> dict:
        if estado.get("bloqueado"):
            return {"messages": [AIMessage(f"Nao posso processar: {estado['bloqueado']}.")]}
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
    out = grafo.invoke({"messages": [HumanMessage(texto)]}, cfg)
    return str(out["messages"][-1].content), out
