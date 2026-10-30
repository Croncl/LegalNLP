import pytest

from cgu_rag import config  # noqa: F401
from cgu_rag.avaliacao import metricas, posicao_do_acerto
from cgu_rag.llm_local import LLMLocal, PoliticaSigiloViolada, endpoint_local


@pytest.mark.parametrize("url,esperado", [
    ("http://localhost:11434/v1", True),
    ("http://127.0.0.1:8080/v1", True),
    ("http://192.168.0.20:11434/v1", True),
    ("http://10.0.0.5:8000/v1", True),
    ("https://api.openai.com/v1", False),
    ("https://modelo.exemplo.com.br/v1", False),
])
def test_endpoint_local(url, esperado):
    assert endpoint_local(url) is esperado


def test_sigilo_falha_fechada():
    with pytest.raises(PoliticaSigiloViolada):
        LLMLocal(base_url="https://api.openai.com/v1", sigilo="sigiloso")


def test_posicao_e_metricas():
    linhas = [{"nota_tecnica": "NT 1", "doc_titulo": "A", "titulo": "x"},
              {"nota_tecnica": "NT 2", "doc_titulo": "B", "titulo": "y"}]
    assert posicao_do_acerto("nt 2", linhas) == 2
    assert posicao_do_acerto("NT 9", linhas) is None
    m = metricas([1, 2, None], k=5)
    assert m["hit@5"] == pytest.approx(0.6667, abs=1e-3)
    assert m["mrr@5"] == pytest.approx((1 + 0.5) / 3, abs=1e-3)


def test_legado_importa():
    from cgu_rag.legado import rag_cgu_pipeline as legado
    assert hasattr(legado, "search") and hasattr(legado, "ingest")
