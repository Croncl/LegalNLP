from cgu_rag.agente.modelo import criar_modelo

URL = "http://localhost:11434/v1"


def test_padrao_nao_altera_os_parametros(monkeypatch):
    monkeypatch.delenv("LLM_PENSAR", raising=False)
    m = criar_modelo(base_url=URL)
    assert m.reasoning_effort is None and not m.extra_body


def test_pensar_false_pelo_parametro_ou_pela_variavel(monkeypatch):
    monkeypatch.delenv("LLM_PENSAR", raising=False)
    m = criar_modelo(base_url=URL, pensar=False)
    assert m.reasoning_effort == "none" and m.extra_body == {"think": False}
    monkeypatch.setenv("LLM_PENSAR", "false")
    m = criar_modelo(base_url=URL)
    assert m.reasoning_effort == "none" and m.extra_body == {"think": False}
    monkeypatch.setenv("LLM_PENSAR", "true")
    assert criar_modelo(base_url=URL).reasoning_effort is None
