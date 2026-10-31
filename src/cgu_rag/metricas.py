"""Metricas de recuperacao, registro de progresso e graficos (passo R3b).

- avaliar(): hit@k e MRR@10, no total e por grupo (fase do PAD, par, fora_do_fluxo).
- registrar(): grava cada medicao em results/progresso.json (idempotente por nome de experimento).
- grafico_*(): desenham os PNG usados no README (matplotlib e importado so quando preciso).
"""
from __future__ import annotations

import json
import time
from pathlib import Path

KS = (1, 3, 5, 10)
PROGRESSO = Path("results/progresso.json")


def acerto(it: dict, r) -> bool:
    """Estrito se o item tem `doc` (mesmo documento, mesma secao, paginas sobrepostas); senao, frouxo."""
    if "doc" in it:
        return (r["doc_titulo"] == it["doc"] and r["titulo"] == it["esperado"]
                and r["pag_ini"] <= it["pag_fim"] and r["pag_fim"] >= it["pag_ini"])
    from .avaliacao import acertou
    return acertou(it["esperado"], r)


def posicao(it: dict, linhas) -> int | None:
    """Posicao (1-based) do primeiro acerto, ou None."""
    return next((i for i, r in enumerate(linhas, 1) if acerto(it, r)), None)


def calcular(posicoes: list) -> dict:
    n = len(posicoes)
    if n == 0:
        return {"n": 0}
    m = {f"hit@{k}": round(sum(1 for p in posicoes if p and p <= k) / n, 4) for k in KS}
    m["mrr@10"] = round(sum(1 / p for p in posicoes if p and p <= max(KS)) / n, 4)
    m["n"] = n
    return m


def grupos_do_item(it: dict) -> list[str]:
    f = it.get("fase")
    if isinstance(f, str):
        f = [f]
    return list(f) if f else ["sem_fase"]


def avaliar(itens: list[dict], buscar_linhas) -> tuple[dict, list]:
    """buscar_linhas(pergunta, k) -> lista de linhas ordenadas. Devolve (metricas, posicoes)."""
    t0, pos = time.time(), []
    for it in itens:
        pos.append(posicao(it, buscar_linhas(it["pergunta"], max(KS))))
    m = calcular(pos)
    m["s_por_consulta"] = round((time.time() - t0) / max(len(itens), 1), 3)
    por: dict[str, list] = {}
    for it, p in zip(itens, pos):
        for g in grupos_do_item(it):
            por.setdefault(g, []).append(p)
    m["por_grupo"] = {g: calcular(ps) for g, ps in por.items()}
    return m, pos


def carregar_progresso(caminho=PROGRESSO) -> list[dict]:
    p = Path(caminho)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def registrar(etapa: str, experimento: str, metricas: dict, caminho=PROGRESSO) -> None:
    p = Path(caminho)
    p.parent.mkdir(parents=True, exist_ok=True)
    h = [x for x in carregar_progresso(p) if x["experimento"] != experimento]
    h.append({"etapa": etapa, "experimento": experimento,
              "quando": time.strftime("%Y-%m-%d %H:%M"), "metricas": metricas})
    p.write_text(json.dumps(h, ensure_ascii=False, indent=2), encoding="utf-8")


def _com_recuperacao(hist):
    return [x for x in hist if "hit@5" in x["metricas"]]


def _salvar(fig, destino):
    import matplotlib.pyplot as plt
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(destino, dpi=130)
    plt.close(fig)
    return destino


def grafico_comparacao(hist: list[dict], destino):
    """Barras hit@k por experimento."""
    exps = _com_recuperacao(hist)
    if not exps:
        return None
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(9, 4))
    larg = 0.8 / len(exps)
    for j, x in enumerate(exps):
        ax.bar([i + j * larg for i in range(len(KS))], [x["metricas"][f"hit@{k}"] for k in KS],
               larg, label=x["experimento"])
    ax.set_xticks([i + 0.4 - larg / 2 for i in range(len(KS))])
    ax.set_xticklabels([f"hit@{k}" for k in KS])
    ax.set_ylim(0, 1.2)
    ax.set_title("Recuperacao por k e por experimento")
    ax.legend(fontsize=8)
    return _salvar(fig, destino)


def grafico_progresso(hist: list[dict], destino):
    """hit@5 e MRR@10 ao longo dos experimentos (ordem de registro)."""
    exps = _com_recuperacao(hist)
    if not exps:
        return None
    import matplotlib.pyplot as plt
    nomes = [x["experimento"] for x in exps]
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(nomes, [x["metricas"]["hit@5"] for x in exps], "o-", label="hit@5")
    ax.plot(nomes, [x["metricas"]["mrr@10"] for x in exps], "s--", label="MRR@10")
    ax.set_ylim(0, 1.2)
    ax.set_title("Progresso da recuperacao")
    ax.legend()
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right")
    return _salvar(fig, destino)


def grafico_por_grupo(hist: list[dict], destino):
    """hit@5 por grupo (fases do PAD, par, fora_do_fluxo) e experimento; o n de cada grupo vai no rotulo."""
    exps = [x for x in _com_recuperacao(hist) if x["metricas"].get("por_grupo")]
    if not exps:
        return None
    import matplotlib.pyplot as plt
    grupos = sorted({g for x in exps for g in x["metricas"]["por_grupo"]})
    fig, ax = plt.subplots(figsize=(10, 4))
    larg = 0.8 / len(exps)
    for j, x in enumerate(exps):
        pg = x["metricas"]["por_grupo"]
        ax.bar([i + j * larg for i in range(len(grupos))],
               [pg.get(g, {}).get("hit@5", 0) for g in grupos], larg, label=x["experimento"])
    ref = exps[-1]["metricas"]["por_grupo"]
    ax.set_xticks([i + 0.4 - larg / 2 for i in range(len(grupos))])
    ax.set_xticklabels([f"{g}\n(n={ref.get(g, {}).get('n', 0)})" for g in grupos], fontsize=8)
    ax.set_ylim(0, 1.2)
    ax.set_title("hit@5 por grupo")
    ax.legend(fontsize=8)
    return _salvar(fig, destino)
