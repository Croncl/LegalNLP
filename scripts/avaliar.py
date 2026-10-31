"""Avalia a recuperacao (BM25 e BM25+vetores) com o gabarito revisado e gera os graficos.

Uso (na raiz do projeto):
  python scripts/avaliar.py                 # mede, registra em results/progresso.json e desenha os graficos
  python scripts/avaliar.py --graficos      # so redesenha os graficos a partir do progresso.json
  python scripts/avaliar.py --gabarito OUTRO.jsonl
O modelo de embeddings vem de RAG_EMB_MODEL e o banco de RAG_DB (.env): troque-os para medir outro modelo.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import matplotlib  # noqa: E402

matplotlib.use("Agg")  # grava PNG sem abrir janela

from cgu_rag import config  # noqa: E402
from cgu_rag import gabarito as gb  # noqa: E402
from cgu_rag import metricas as mt  # noqa: E402

GRAFICOS = (("03_comparacao.png", mt.grafico_comparacao),
            ("04_progresso.png", mt.grafico_progresso),
            ("05_por_grupo.png", mt.grafico_por_grupo))


def graficos():
    hist = mt.carregar_progresso()
    for nome, fn in GRAFICOS:
        out = fn(hist, Path("results") / nome)
        print("grafico:", out if out else f"{nome} (sem dados)")


def medir(caminho):
    itens = gb.carregar(caminho)
    if not itens or any("TROQUE-PELA" in str(i.get("esperado", "")) for i in itens):
        raise SystemExit("ERRO: gabarito vazio ou ainda e o texto-modelo. Rode: python scripts/gabarito.py exportar")
    from cgu_rag.busca import abrir_db, buscar
    con = abrir_db()
    emb = config.settings.emb_model
    print(f"{len(itens)} perguntas | embeddings: {emb} | banco: {config.settings.db_path}")
    for nome, denso in (("BM25", False), (f"BM25+vetores ({emb})", True)):
        m, _ = mt.avaliar(itens, lambda q, k, d=denso: [r for _, r in buscar(con, q, k, d)])
        m.update({"emb_model": emb, "db": config.settings.db_path, "gabarito": str(caminho)})
        mt.registrar("recuperacao", nome, m)
        print(f"\n{nome}: " + " ".join(f"{k}={m[k]}" for k in ("hit@1", "hit@3", "hit@5", "hit@10", "mrr@10", "s_por_consulta")))
        for g, mg in m["por_grupo"].items():
            print(f"   {g:16s} n={mg['n']:3d} hit@5={mg.get('hit@5')} mrr@10={mg.get('mrr@10')}")
    graficos()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Avaliacao da recuperacao")
    ap.add_argument("--gabarito", default="data/gabarito/perguntas.jsonl")
    ap.add_argument("--graficos", action="store_true", help="so redesenha os graficos")
    a = ap.parse_args()
    graficos() if a.graficos else medir(a.gabarito)
