import pytest

from cgu_rag import gabarito as gb


def itens():
    return [
        {"id": "q01", "pergunta": "A?", "esperado": "Sec 1", "doc": "D", "pag_ini": 1, "pag_fim": 2, "origem": "sintetico"},
        {"id": "q02", "pergunta": "B?", "esperado": "Sec 2", "doc": "D", "pag_ini": 3, "pag_fim": 4, "origem": "sintetico"},
        {"id": "q03", "pergunta": "C?", "esperado": "Sec 3", "doc": "D", "pag_ini": 5, "pag_fim": 6, "origem": "sintetico"},
    ]


def test_preparar_e_idempotente_e_migra_fase_antiga():
    a = gb.preparar(itens())
    a[0].update(status="aprovado", fase="acusatoria")
    assert gb.preparar(a)[0]["fase"] == ["acusatoria"]
    assert len(gb.pendentes(a)) == 2


def test_fase_invalida_ou_vazia():
    it = gb.preparar(itens())[0]
    for ruim in ("geral", "tac", [], ["julgamento", "tac"], ["fora_do_fluxo", "julgamento"], ["par", "julgamento"]):
        with pytest.raises(ValueError):
            gb.aplicar(it, "aprovar", fase=ruim)


def test_interpretar_fase():
    assert gb.interpretar_fase("1") == ["admissibilidade"]
    assert gb.interpretar_fase("31") == ["admissibilidade", "julgamento"]
    assert gb.interpretar_fase("123") == list(gb.FASES)
    assert gb.interpretar_fase("0") == ["fora_do_fluxo"]
    assert gb.interpretar_fase("4") == ["par"]
    assert gb.interpretar_fase("") is None
    for ruim in ("5", "01", "14"):
        with pytest.raises(ValueError):
            gb.interpretar_fase(ruim)


def test_editar_atualiza_pergunta_e_marca_editada():
    it = gb.preparar(itens())[0]
    gb.aplicar(it, "editar", fase="julgamento", pergunta="  Nova?  ")
    assert it["pergunta"] == "Nova?" and it["editada"] is True and it["fase"] == ["julgamento"]
    with pytest.raises(ValueError):
        gb.aplicar(gb.preparar(itens())[1], "editar", fase="julgamento", pergunta=" ")


def test_resumo_conta_por_fase_transversal_e_fora():
    a = gb.preparar(itens())
    gb.aplicar(a[0], "aprovar", fase=["admissibilidade"])
    gb.aplicar(a[1], "aprovar", fase=list(gb.FASES))
    gb.aplicar(a[2], "aprovar", fase=["fora_do_fluxo"])
    r = gb.resumo(a)
    assert r["por_fase"] == {"admissibilidade": 2, "acusatoria": 1, "julgamento": 1}
    assert r["transversais"] == 1 and r["fora_do_fluxo"] == 1 and r["par"] == 0


def test_par_e_categoria_propria_e_nao_conta_nas_fases():
    a = gb.preparar(itens())
    gb.aplicar(a[0], "aprovar", fase=["par"])
    r = gb.resumo(a)
    assert r["par"] == 1 and sum(r["por_fase"].values()) == 0
    assert gb.exportar(a)[0]["fase"] == ["par"]


def test_exportar_so_aprovadas_com_fase_lista_e_origem():
    a = gb.preparar(itens())
    gb.aplicar(a[0], "aprovar", fase=["admissibilidade", "acusatoria"])
    gb.aplicar(a[1], "editar", fase="julgamento", pergunta="B2?")
    gb.aplicar(a[2], "descartar")
    out = gb.exportar(a)
    assert [o["id"] for o in out] == ["q01", "q02"]
    assert out[0]["fase"] == ["admissibilidade", "acusatoria"] and out[0]["origem"] == "sintetico_revisado"
    assert out[1]["origem"] == "sintetico_editado" and "status" not in out[0]


def test_salvar_e_carregar(tmp_path):
    p = tmp_path / "x" / "r.jsonl"
    gb.salvar(p, gb.preparar(itens()))
    assert gb.carregar(p)[1]["id"] == "q02"
