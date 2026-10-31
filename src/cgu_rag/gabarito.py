"""Gabarito de avaliacao com revisao humana (decisoes D-08 e D-11).

Fluxo: rascunho.jsonl (perguntas candidatas) -> revisao humana -> perguntas.jsonl (so as aprovadas).
Campo `fase` (D-11): lista com uma ou mais das tres fases do PAD, ou um valor exclusivo:
`par` (processo de responsabilizacao, outro rito) ou `fora_do_fluxo`.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

FASES = ("admissibilidade", "acusatoria", "julgamento")
FORA = "fora_do_fluxo"
PAR = "par"
CAMPOS_EXPORT = ("id", "pergunta", "esperado", "doc", "pag_ini", "pag_fim", "fase")


def carregar(caminho) -> list[dict]:
    texto = Path(caminho).read_text(encoding="utf-8")
    return [json.loads(l) for l in texto.splitlines() if l.strip()]


def salvar(caminho, itens: list[dict]) -> None:
    p = Path(caminho)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text("\n".join(json.dumps(i, ensure_ascii=False) for i in itens) + "\n", encoding="utf-8")
    os.replace(tmp, p)  # troca atomica: nunca deixa o arquivo pela metade


def normalizar_fase(fase) -> list[str]:
    """Aceita texto ou lista; devolve a lista valida (ordem canonica) ou levanta ValueError."""
    if isinstance(fase, str):
        fase = [fase]
    fase = list(dict.fromkeys(fase or []))
    if not fase:
        raise ValueError("informe ao menos uma fase")
    for exclusivo in (FORA, PAR):
        if exclusivo in fase:
            if len(fase) > 1:
                raise ValueError(f"{exclusivo} nao pode ser combinado com outras categorias")
            return [exclusivo]
    invalidas = [f for f in fase if f not in FASES]
    if invalidas:
        raise ValueError(f"fase invalida: {invalidas}. Use {FASES}, {PAR!r} ou {FORA!r}")
    return [f for f in FASES if f in fase]


def interpretar_fase(texto: str):
    """Digitos '1','2','3' (combinaveis: '13'), '4' (PAR) ou '0' (fora do fluxo). Vazio = None (voltar)."""
    s = "".join(ch for ch in texto if ch.isdigit())
    if not s:
        return None
    if s == "0":
        return [FORA]
    if s == "4":
        return [PAR]
    if any(ch not in "123" for ch in s):
        raise ValueError("use 1, 2 ou 3 (combinados, ex.: 13), 4 para PAR ou 0 para fora do fluxo")
    return normalizar_fase([FASES[int(ch) - 1] for ch in s])


def preparar(itens: list[dict]) -> list[dict]:
    for it in itens:
        it.setdefault("status", "pendente")
        it.setdefault("fase", None)
        if isinstance(it["fase"], str):  # migra o formato antigo (uma fase so)
            it["fase"] = [it["fase"]]
    return itens


def pendentes(itens: list[dict]) -> list[dict]:
    return [i for i in itens if i.get("status") == "pendente"]


def aplicar(item: dict, acao: str, fase=None, pergunta: str | None = None) -> dict:
    if acao == "descartar":
        item["status"], item["fase"] = "descartado", None
        return item
    if acao not in ("aprovar", "editar"):
        raise ValueError(f"acao desconhecida: {acao}")
    fase = normalizar_fase(fase)
    if acao == "editar":
        if not pergunta or not pergunta.strip():
            raise ValueError("pergunta editada nao pode ser vazia")
        item["pergunta"], item["editada"] = pergunta.strip(), True
    item["status"], item["fase"] = "aprovado", fase
    return item


def resumo(itens: list[dict]) -> dict:
    r = {"total": len(itens), "pendente": 0, "aprovado": 0, "descartado": 0}
    por_fase = {f: 0 for f in FASES}
    transversais = fora = par = 0
    for i in itens:
        r[i.get("status", "pendente")] += 1
        if i.get("status") != "aprovado":
            continue
        fs = normalizar_fase(i.get("fase"))
        if fs == [PAR]:
            par += 1
            continue
        if fs == [FORA]:
            fora += 1
            continue
        for f in fs:
            por_fase[f] += 1
        transversais += len(fs) == len(FASES)
    r.update({"por_fase": por_fase, "transversais": transversais, PAR: par, FORA: fora})
    return r


def exportar(itens: list[dict]) -> list[dict]:
    saida = []
    for i in itens:
        if i.get("status") != "aprovado":
            continue
        d = {k: i[k] for k in CAMPOS_EXPORT if k in i}
        d["fase"] = normalizar_fase(i.get("fase"))
        d["origem"] = "sintetico_editado" if i.get("editada") else "sintetico_revisado"
        saida.append(d)
    return saida
