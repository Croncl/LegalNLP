"""Grafo LangGraph do assistente: estado, nos, arestas e memoria por conversa (D-14, D-15).

Fluxo:  entrada -> (bloqueado? saida : responder) ; responder -> (pediu ferramenta? ferramentas -> responder : saida)
- entrada:     normaliza o turno e zera ferramentas/skills usadas (ponto do guardrail de entrada, R11)
- responder:   o modelo decide: responder ou chamar a ferramenta de consulta (RAG agentico, D-15)
- ferramentas: executa a consulta; o resultado volta ao modelo, que pode reformular e consultar de novo
- saida:       registra as ferramentas do turno e entrega a resposta ou a recusa (guardrail de saida, R11)
Memoria: checkpointer por thread_id (uma conversa = uma thread).
"""
from __future__ import annotations

from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

PROMPT_SISTEMA = (
    "Voce e um assistente sobre processos de correicao da CGU: processo administrativo disciplinar (PAD) "
    "e processo administrativo de responsabilizacao (PAR). Responda em portugues, de forma objetiva. "
    "Se nao souber, diga que nao sabe."
)
PROMPT_RAG = (
    "Você é um assistente sobre processos de correição da CGU: processo administrativo disciplinar (PAD) "
    "e processo administrativo de responsabilização (PAR). Responda em português, de forma objetiva.\n"
    "Para perguntas sobre normas, prazos, ritos ou conceitos, SEMPRE use a ferramenta consultar_base antes de "
    "responder. Se os trechos não responderem, reformule a consulta (outros termos, sinônimos, termo técnico) "
    "e consulte de novo, no máximo 3 consultas. Responda SOMENTE com base nos trechos, citando a fonte no formato "
    "[documento, págs X-Y]. Se, depois de consultar, não houver evidência, diga que não encontrou nos documentos. "
    "Para saudações e conversa simples, não consulte."
)
MAX_MSGS = 10       # mensagens recentes enviadas ao modelo (o contexto do modelo local e limitado)
MAX_CONSULTAS = 3   # consultas por turno; depois disso o modelo e obrigado a responder


class Estado(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]  # historico da conversa
    bloqueado: str        # motivo da recusa; vazio se liberado
    ferramentas: list     # ferramentas chamadas neste turno (a interface exibe)
    skills: list          # skills carregadas neste turno (a interface exibe)


def _humana_vazia(m) -> bool:
    return isinstance(m, HumanMessage) and not str(m.content).strip()


def recentes(mensagens: list, max_msgs: int) -> list:
    """Historico enviado ao modelo: sem mensagens vazias do usuario e, nos turnos ANTERIORES, sem chamadas e
    resultados de ferramenta (so pergunta e resposta final; o resultado das consultas pesa no contexto).
    O turno atual fica completo. A lista comeca sempre por uma mensagem do usuario."""
    msgs = [m for m in mensagens if not _humana_vazia(m)]
    ult = max((i for i, m in enumerate(msgs) if isinstance(m, HumanMessage)), default=0)
    antes = [m for m in msgs[:ult]
             if not isinstance(m, ToolMessage) and not (isinstance(m, AIMessage) and m.tool_calls)]
    atual = msgs[ult:]
    espaco = max(max_msgs - len(atual), 0)  # o turno atual nunca e cortado
    sel = (antes[-espaco:] if espaco else []) + atual
    while sel and not isinstance(sel[0], HumanMessage):
        sel.pop(0)
    return sel


def consultas_no_turno(mensagens: list) -> int:
    n = 0
    for m in reversed(mensagens):
        if isinstance(m, HumanMessage):
            break
        n += isinstance(m, ToolMessage)
    return n


def chamadas_do_turno(mensagens: list) -> list[dict]:
    chamadas: list[dict] = []
    for m in reversed(mensagens):
        if isinstance(m, HumanMessage):
            break
        if isinstance(m, AIMessage):
            chamadas = [{"nome": c["name"], "args": c["args"]} for c in m.tool_calls] + chamadas
    return chamadas


def criar_grafo(modelo, max_msgs: int = MAX_MSGS, checkpointer=None, ferramentas: list | None = None,
                max_consultas: int = MAX_CONSULTAS, prompt: str | None = None):
    """`modelo` e qualquer objeto com invoke(mensagens) -> AIMessage (e bind_tools, se houver ferramentas)."""
    ferramentas = ferramentas or []
    com_ferramentas = modelo.bind_tools(ferramentas) if ferramentas else modelo
    prompt = prompt or (PROMPT_RAG if ferramentas else PROMPT_SISTEMA)

    def entrada(estado: Estado) -> dict:
        vazio = _humana_vazia(estado["messages"][-1])
        return {"bloqueado": "mensagem vazia" if vazio else "", "ferramentas": [], "skills": []}

    def responder(estado: Estado) -> dict:
        msgs = estado["messages"]
        usar = com_ferramentas if consultas_no_turno(msgs) < max_consultas else modelo  # limite: responde sem ferramenta
        return {"messages": [usar.invoke([SystemMessage(prompt)] + recentes(msgs, max_msgs))]}

    def saida(estado: Estado) -> dict:
        out: dict = {"ferramentas": chamadas_do_turno(estado["messages"])}
        if estado.get("bloqueado"):
            out["messages"] = [AIMessage(f"Nao posso processar: {estado['bloqueado']}.")]
        return out

    def rota_entrada(estado: Estado) -> str:
        return "saida" if estado.get("bloqueado") else "responder"

    def rota_responder(estado: Estado) -> str:
        return "ferramentas" if getattr(estado["messages"][-1], "tool_calls", None) else "saida"

    g = StateGraph(Estado)
    g.add_node("entrada", entrada)
    g.add_node("responder", responder)
    g.add_node("saida", saida)
    g.add_edge(START, "entrada")
    g.add_conditional_edges("entrada", rota_entrada, {"responder": "responder", "saida": "saida"})
    if ferramentas:
        g.add_node("ferramentas", ToolNode(ferramentas))
        g.add_conditional_edges("responder", rota_responder, {"ferramentas": "ferramentas", "saida": "saida"})
        g.add_edge("ferramentas", "responder")
    else:
        g.add_edge("responder", "saida")
    g.add_edge("saida", END)
    return g.compile(checkpointer=checkpointer or MemorySaver())


def conversar(grafo, texto: str, thread_id: str) -> tuple[str, dict]:
    """Um turno. Devolve (resposta, estado final). O thread_id identifica a conversa."""
    cfg = {"configurable": {"thread_id": thread_id}}
    out = grafo.invoke({"messages": [HumanMessage(texto)]}, cfg)
    return str(out["messages"][-1].content), out
