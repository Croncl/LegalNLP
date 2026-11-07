"""Mede o comportamento do agente (RAG agentico) sobre o gabarito revisado, para um modelo.

Uso (na raiz do projeto, com o Ollama rodando):
  python scripts/medir_agente.py --modelo qwen2.5:7b --n 8
Mede: % de perguntas em que o agente consultou a base; % em que a consulta trouxe a secao esperada
(acerto estrito); numero medio de consultas; % de respostas com pagina citada SEM consulta (possivel invencao);
tempo por pergunta. Grava em results/progresso.json e detalha em results/agente_<modelo>.jsonl.
"""
import argparse
import json
import random
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cgu_rag import metricas as mt  # noqa: E402
from cgu_rag.agente.ferramentas import criar_buscador, criar_ferramenta_consulta  # noqa: E402
from cgu_rag.agente.grafo import conversar, criar_grafo  # noqa: E402
from cgu_rag.agente.modelo import criar_modelo  # noqa: E402

CITA_PAGINA = re.compile(r"p[aá]gs?\.?\s*\d", re.I)


def media(xs):
    return round(sum(xs) / len(xs), 3) if xs else 0.0


def medir(nome_modelo: str, itens: list[dict]) -> tuple[dict, list[dict]]:
    base, log = criar_buscador(), []

    def buscador(q, k):
        linhas = base(q, k)
        log.append(linhas)
        return linhas

    grafo = criar_grafo(criar_modelo(model=nome_modelo), ferramentas=[criar_ferramenta_consulta(buscador)])
    detalhes = []
    for i, it in enumerate(itens):
        log.clear()
        t0 = time.time()
        try:
            resposta, estado = conversar(grafo, it["pergunta"], f"m{i}")
        except Exception as e:  # nao interrompe a medicao
            resposta, estado = f"ERRO: {e}", {"ferramentas": []}
        chamadas = estado.get("ferramentas", [])
        linhas = [r for lote in log for r in lote]
        pos = mt.posicao(it, linhas) if linhas else None
        detalhes.append({
            "id": it["id"], "pergunta": it["pergunta"], "consultas": [c["args"].get("consulta") for c in chamadas],
            "posicao_do_acerto": pos, "citou_pagina": bool(CITA_PAGINA.search(resposta)),
            "segundos": round(time.time() - t0, 1), "resposta": resposta[:400]})
        print(f"[{i + 1}/{len(itens)}] consultas={len(chamadas)} acerto={'sim' if pos else 'nao'} {detalhes[-1]['segundos']}s")
    m = {
        "n": len(detalhes),
        "consultou": media([bool(d["consultas"]) for d in detalhes]),
        "acerto_na_consulta": media([d["posicao_do_acerto"] is not None for d in detalhes]),
        "consultas_medias": media([len(d["consultas"]) for d in detalhes]),
        "citou_sem_consultar": media([d["citou_pagina"] and not d["consultas"] for d in detalhes]),
        "s_por_pergunta": media([d["segundos"] for d in detalhes]),
        "modelo": nome_modelo,
    }
    return m, detalhes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", required=True)
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--gabarito", default="data/gabarito/perguntas.jsonl")
    a = ap.parse_args()
    itens = [json.loads(l) for l in Path(a.gabarito).read_text(encoding="utf-8").splitlines() if l.strip()]
    itens = random.Random(42).sample(itens, min(a.n, len(itens)))  # mesma amostra para todos os modelos
    m, detalhes = medir(a.modelo, itens)
    mt.registrar("agente", f"Agente {a.modelo} (n={m['n']})", m)
    saida = Path("results") / f"agente_{re.sub(r'[^A-Za-z0-9.]+', '_', a.modelo)}.jsonl"
    saida.parent.mkdir(exist_ok=True)
    saida.write_text("\n".join(json.dumps(d, ensure_ascii=False) for d in detalhes), encoding="utf-8")
    print("\n" + json.dumps(m, ensure_ascii=False, indent=1))
    print("detalhes em", saida)


if __name__ == "__main__":
    main()
