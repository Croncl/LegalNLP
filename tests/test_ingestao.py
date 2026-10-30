import cgu_rag.ingestao as ing
from cgu_rag.ingestao import arquivo_da_fonte, listar_fontes, obter_bytes

URL = "https://x.gov.br/bitstreams/ec9c2e26-8443-4cae-9d65-7abea5076ca3/download"


def test_nome_do_arquivo_vem_do_id_do_bitstream():
    assert arquivo_da_fonte(URL, "p").name == "ec9c2e26-8443-4cae-9d65-7abea5076ca3.pdf"


def test_listar_fontes_inclui_pdf_local_extra(tmp_path):
    (tmp_path / "meu.pdf").write_bytes(b"%PDF-1.4")
    assert any(x.endswith("meu.pdf") for x in listar_fontes([], str(tmp_path)))


def test_pdf_ja_na_pasta_nao_baixa(tmp_path, monkeypatch):
    arquivo_da_fonte(URL, str(tmp_path)).write_bytes(b"abc")

    def proibido(*a, **k):
        raise AssertionError("nao deveria baixar")

    monkeypatch.setattr(ing.requests, "get", proibido)
    assert obter_bytes(URL, str(tmp_path)) == b"abc"


def test_link_conhecido_nao_vira_fonte_local_duplicada(tmp_path):
    arquivo_da_fonte(URL, str(tmp_path)).write_bytes(b"abc")
    assert listar_fontes([URL], str(tmp_path)) == [URL]
