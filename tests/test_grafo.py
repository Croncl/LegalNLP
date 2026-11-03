import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from cgu_rag.agente.grafo import conversar, criar_grafo, recentes
from cgu_rag.agente.modelo import criar_modelo
from cgu_rag.llm_local import PoliticaSigiloViolada


class ModeloFalso:
    def __init__(self):
        self.chamadas = []

    def invoke(self, mensagens, **kw):
        self.chamadas.append(mensagens)
        return AIMessage(f"resposta {len(self.chamadas)}")


def conteudos(chamada):
    return [m.content for m in chamada]


def test_memoria_na_mesma_thread():
    llm = ModeloFalso()
    g = criar_grafo(llm)
    conversar(g, "Meu nome e Ana", "t1")
    conversar(g, "Qual e o meu nome?", "t1")
    assert conteudos(llm.chamadas[1])[1:] == ["Meu nome e Ana", "resposta 1", "Qual e o meu nome?"]
    assert llm.chamadas[1][0].type == "system"


def test_threads_sao_isoladas():
    llm = ModeloFalso()
    g = criar_grafo(llm)
    conversar(g, "Meu nome e Ana", "t1")
    conversar(g, "Oi", "t2")
    assert conteudos(llm.chamadas[1])[1:] == ["Oi"]


def test_mensagem_vazia_nao_chama_o_modelo():
    llm = ModeloFalso()
    g = criar_grafo(llm)
    resposta, estado = conversar(g, "   ", "t1")
    assert llm.chamadas == [] and "vazia" in resposta and estado["bloqueado"] == "mensagem vazia"


def test_vazio_nao_polui_o_historico_enviado_ao_modelo():
    llm = ModeloFalso()
    g = criar_grafo(llm)
    conversar(g, "", "t1")
    conversar(g, "Pergunta real", "t1")
    assert "" not in conteudos(llm.chamadas[0])[1:]
    assert conteudos(llm.chamadas[0])[-1] == "Pergunta real"


def test_historico_enviado_e_limitado_mas_o_estado_guarda_tudo():
    llm = ModeloFalso()
    g = criar_grafo(llm, max_msgs=3)
    for i in range(4):
        _, estado = conversar(g, f"p{i}", "t1")
    assert len(llm.chamadas[-1]) <= 1 + 3          # system + ate 3 recentes
    assert llm.chamadas[-1][1].type == "human"     # comeca sempre por mensagem do usuario
    assert len(estado["messages"]) == 8            # 4 perguntas + 4 respostas guardadas


def test_recentes_tira_ferramentas_de_turnos_anteriores_e_mantem_o_turno_atual():
    antigo = [HumanMessage("a"), AIMessage("", tool_calls=[{"name": "f", "args": {}, "id": "1"}]),
              ToolMessage("r", tool_call_id="1"), AIMessage("ok")]
    atual = [HumanMessage("b"), AIMessage("", tool_calls=[{"name": "f", "args": {}, "id": "2"}]),
             ToolMessage("r2", tool_call_id="2")]
    assert [m.type for m in recentes(antigo + atual, 10)] == ["human", "ai", "human", "ai", "tool"]
    assert [m.content for m in recentes(antigo + atual, 3)] == ["b", "", "r2"]  # turno atual nunca e cortado
    assert recentes(antigo + atual, 1)[0].content == "b"


def test_ferramentas_e_skills_zeradas_a_cada_turno():
    g = criar_grafo(ModeloFalso())
    _, estado = conversar(g, "oi", "t1")
    assert estado["ferramentas"] == [] and estado["skills"] == []


def test_sigilo_bloqueia_endpoint_externo():
    with pytest.raises(PoliticaSigiloViolada):
        criar_modelo(base_url="https://api.openai.com/v1", sigilo="sigiloso")
    assert criar_modelo(base_url="http://localhost:11434/v1", sigilo="sigiloso") is not None
