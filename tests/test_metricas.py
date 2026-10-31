import pytest

from cgu_rag import metricas as mt


def linha(doc="D", titulo="Sec 1", ini=1, fim=2, nt=None):
    return {"doc_titulo": doc, "titulo": titulo, "pag_ini": ini, "pag_fim": fim, "nota_tecnica": nt}


ITEM = {"id": "q1", "pergunta": "?", "esperado": "Sec 1", "doc": "D", "pag_ini": 1, "pag_fim": 2, "fase": ["admissibilidade"]}


def test_acerto_estrito_exige_doc_secao_e_paginas():
    assert mt.acerto(ITEM, linha())
    assert not mt.acerto(ITEM, linha(doc="X"))
    assert not mt.acerto(ITEM, linha(titulo="Outra"))
    assert not mt.acerto(ITEM, linha(ini=5, fim=6))
    assert mt.acerto(ITEM, linha(ini=2, fim=3))  # paginas sobrepostas


def test_acerto_frouxo_sem_campo_doc():
    it = {"pergunta": "?", "esperado": "nota tecnica 1"}
    assert mt.acerto(it, linha(nt="Nota Tecnica 1/2023"))
    assert not mt.acerto(it, linha(nt="Outra"))


def test_posicao_e_calcular():
    assert mt.posicao(ITEM, [linha(titulo="x"), linha()]) == 2
    assert mt.posicao(ITEM, [linha(titulo="x")]) is None
    m = mt.calcular([1, 2, None, 11])
    assert m["hit@1"] == 0.25 and m["hit@3"] == 0.5 and m["hit@10"] == 0.5
    assert m["mrr@10"] == pytest.approx((1 + 0.5) / 4, abs=1e-3)
    assert mt.calcular([]) == {"n": 0}


def test_avaliar_com_grupos_e_par():
    itens = [dict(ITEM, id="a", fase=["admissibilidade", "julgamento"]),
             dict(ITEM, id="b", fase=["par"], esperado="Sec 2"),
             dict(ITEM, id="c", fase=["fora_do_fluxo"], esperado="Sec 3")]
    base = {"?": [linha(), linha(titulo="Sec 2")]}
    m, pos = mt.avaliar(itens, lambda q, k: base["?"])
    assert pos == [1, 2, None]
    assert set(m["por_grupo"]) == {"admissibilidade", "julgamento", "par", "fora_do_fluxo"}
    assert m["por_grupo"]["par"]["hit@3"] == 1.0 and m["por_grupo"]["fora_do_fluxo"]["hit@10"] == 0.0


def test_registrar_e_idempotente_por_experimento(tmp_path):
    p = tmp_path / "r" / "progresso.json"
    mt.registrar("x", "A", {"hit@5": 0.1}, p)
    mt.registrar("x", "B", {"hit@5": 0.2}, p)
    mt.registrar("x", "A", {"hit@5": 0.3}, p)
    h = mt.carregar_progresso(p)
    assert [x["experimento"] for x in h] == ["B", "A"] and h[1]["metricas"]["hit@5"] == 0.3


def test_graficos_geram_png(tmp_path):
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg")
    pg = {"par": {"hit@5": 0.5, "n": 2}, "admissibilidade": {"hit@5": 1.0, "n": 3}}
    hist = [{"experimento": e, "metricas": {**{f"hit@{k}": v for k in mt.KS}, "mrr@10": v, "por_grupo": pg}}
            for e, v in (("A1", 0.4), ("A2", 0.6))]
    for fn, nome in ((mt.grafico_comparacao, "a.png"), (mt.grafico_progresso, "b.png"), (mt.grafico_por_grupo, "c.png")):
        out = fn(hist, tmp_path / nome)
        assert out.exists() and out.stat().st_size > 1000
    assert mt.grafico_progresso([], tmp_path / "z.png") is None
