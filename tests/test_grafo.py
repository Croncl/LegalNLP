from cgu_rag.agente.grafo import criar_grafo, conversar


class LLMFalso:
    def __init__(self):
        self.chamadas = []

    def chat(self, mensagens, **kw):
        self.chamadas.append(mensagens)
        return f"resposta {len(self.chamadas)}"


def conteudos(chamada):
    return [m["content"] for m in chamada]


def test_memoria_na_mesma_thread():
    llm = LLMFalso()
    g = criar_grafo(llm)
    conversar(g, "Meu nome e Ana", "t1")
    conversar(g, "Qual e o meu nome?", "t1")
    assert conteudos(llm.chamadas[1])[1:] == ["Meu nome e Ana", "resposta 1", "Qual e o meu nome?"]
    assert llm.chamadas[1][0]["role"] == "system"


def test_threads_sao_isoladas():
    llm = LLMFalso()
    g = criar_grafo(llm)
    conversar(g, "Meu nome e Ana", "t1")
    conversar(g, "Oi", "t2")
    assert conteudos(llm.chamadas[1])[1:] == ["Oi"]


def test_mensagem_vazia_nao_chama_o_llm():
    llm = LLMFalso()
    g = criar_grafo(llm)
    resposta, estado = conversar(g, "   ", "t1")
    assert llm.chamadas == [] and "vazia" in resposta and estado["bloqueado"] == "mensagem vazia"


def test_vazio_nao_polui_o_historico_enviado_ao_llm():
    llm = LLMFalso()
    g = criar_grafo(llm)
    conversar(g, "", "t1")
    conversar(g, "Pergunta real", "t1")
    assert "" not in conteudos(llm.chamadas[0])[1:]
    assert conteudos(llm.chamadas[0])[-1] == "Pergunta real"


def test_historico_enviado_e_limitado_mas_o_estado_guarda_tudo():
    llm = LLMFalso()
    g = criar_grafo(llm, max_msgs=3)
    for i in range(4):
        _, estado = conversar(g, f"p{i}", "t1")
    assert len(llm.chamadas[-1]) == 1 + 3          # system + 3 recentes
    assert len(estado["messages"]) == 8            # 4 perguntas + 4 respostas guardadas


def test_ferramentas_e_skills_zeradas_a_cada_turno():
    g = criar_grafo(LLMFalso())
    _, estado = conversar(g, "oi", "t1")
    assert estado["ferramentas"] == [] and estado["skills"] == []
