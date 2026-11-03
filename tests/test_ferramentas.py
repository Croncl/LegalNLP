from langchain_core.messages import AIMessage, ToolMessage

from cgu_rag.agente.ferramentas import criar_ferramenta_consulta, formatar_trechos
from cgu_rag.agente.grafo import conversar, criar_grafo


def linha(i=1, texto="texto " * 300, nt=None, link="http://x/y"):
    return {"nota_tecnica": nt, "doc_titulo": "Manual PAD", "secao": "3.1", "titulo": "Prazos",
            "pag_ini": i, "pag_fim": i + 1, "texto": texto, "link_fonte": link}


def chamada(consulta, id="c1"):
    return AIMessage("", tool_calls=[{"name": "consultar_base", "args": {"consulta": consulta}, "id": id}])


class ModeloRoteirizado:
    """Com ferramentas: segue o roteiro. Sem ferramentas: responde direto (limite de consultas)."""

    def __init__(self, roteiro):
        self.roteiro, self.com, self.sem = list(roteiro), [], []

    def bind_tools(self, ferramentas):
        dono = self

        class ComFerramentas:
            def invoke(self, msgs, **kw):
                dono.com.append(msgs)
                return dono.roteiro.pop(0) if dono.roteiro else AIMessage("fim")

        return ComFerramentas()

    def invoke(self, msgs, **kw):
        self.sem.append(msgs)
        return AIMessage("resposta forcada")


def montar(roteiro, **kw):
    consultas = []

    def buscador(q, k):
        consultas.append((q, k))
        return [linha(1), linha(5)]

    modelo = ModeloRoteirizado(roteiro)
    grafo = criar_grafo(modelo, ferramentas=[criar_ferramenta_consulta(buscador)], **kw)
    return modelo, grafo, consultas


def test_formatar_trechos_traz_fonte_paginas_link_e_limita_o_texto():
    s = formatar_trechos([linha(7)], max_car=100)
    assert "Manual PAD" in s and "pags 7-8" in s and "http://x/y" in s
    assert len(s.split("\n", 1)[1]) <= 100
    assert "Nota Tecnica 1" in formatar_trechos([linha(nt="Nota Tecnica 1")])
    assert "Nenhum trecho" in formatar_trechos([])


def test_consulta_e_resposta_com_a_fonte():
    modelo, g, consultas = montar([chamada("prazo pad"), AIMessage("Resposta [Manual PAD, pags 1-2]")])
    resposta, estado = conversar(g, "Qual o prazo do PAD?", "t1")
    assert resposta.startswith("Resposta") and consultas == [("prazo pad", 4)]
    assert estado["ferramentas"] == [{"nome": "consultar_base", "args": {"consulta": "prazo pad"}}]
    assert "Manual PAD" in modelo.com[1][-1].content  # o resultado da consulta voltou ao modelo


def test_reformula_e_busca_de_novo():
    _, g, consultas = montar([chamada("q1", "a"), chamada("q2", "b"), AIMessage("final")])
    resposta, estado = conversar(g, "pergunta vaga", "t1")
    assert resposta == "final" and [c[0] for c in consultas] == ["q1", "q2"]
    assert [c["args"]["consulta"] for c in estado["ferramentas"]] == ["q1", "q2"]


def test_limite_de_consultas_forca_a_resposta():
    modelo, g, consultas = montar([chamada(f"q{i}", f"id{i}") for i in range(10)], max_consultas=2)
    resposta, estado = conversar(g, "pergunta", "t1")
    assert resposta == "resposta forcada" and len(consultas) == 2 and len(estado["ferramentas"]) == 2


def test_saudacao_nao_consulta():
    _, g, consultas = montar([AIMessage("Ola!")])
    resposta, estado = conversar(g, "oi", "t1")
    assert resposta == "Ola!" and consultas == [] and estado["ferramentas"] == []


def test_ferramentas_do_turno_nao_vazam_para_o_proximo_e_o_historico_fica_enxuto():
    modelo, g, _ = montar([chamada("q1"), AIMessage("resposta 1"), AIMessage("resposta 2")])
    conversar(g, "primeira", "t1")
    _, estado = conversar(g, "segunda", "t1")
    assert estado["ferramentas"] == []
    enviado = modelo.com[-1]
    assert not any(isinstance(m, ToolMessage) for m in enviado)           # resultado antigo nao volta ao contexto
    assert [m.content for m in enviado if m.type in ("human", "ai")] == ["primeira", "resposta 1", "segunda"]
