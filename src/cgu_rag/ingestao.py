"""Ingestao dos PDFs no banco (passo R2). Move para um modulo o que antes era uma celula do notebook.

- Se o PDF ja esta em data/pdfs/ (nome = id do bitstream), nao baixa; senao baixa e salva la.
- PDFs com outros nomes na pasta entram como fontes locais extras.
- A extracao, limpeza e segmentacao continuam no modulo legado (baseline, sem alteracoes).
"""
from __future__ import annotations

import hashlib
import re
import time
from pathlib import Path

import requests

from . import config  # noqa: F401  (define RAG_DB e RAG_EMB_MODEL antes do legado)
from .fontes import FONTES, PASTA_PDFS


def _legado():
    from .legado import rag_cgu_pipeline as legado
    return legado


def _e_link(src: str) -> bool:
    return bool(re.match(r"https?://", src))


def arquivo_da_fonte(src: str, pasta: str = PASTA_PDFS) -> Path:
    m = re.search(r"/bitstreams/([0-9a-fA-F-]{36})/", src)
    nome = m.group(1) if m else hashlib.sha1(src.encode()).hexdigest()[:12]
    return Path(pasta) / f"{nome}.pdf"


def obter_bytes(src: str, pasta: str = PASTA_PDFS, tentativas: int = 3) -> bytes:
    if not _e_link(src):
        return Path(src).read_bytes()
    arq = arquivo_da_fonte(src, pasta)
    if arq.exists() and arq.stat().st_size > 0:
        print(f"  na pasta, sem baixar: {arq.name}")
        return arq.read_bytes()
    arq.parent.mkdir(parents=True, exist_ok=True)
    ultimo = None
    for t in range(1, tentativas + 1):
        try:
            r = requests.get(src, timeout=180, headers={"User-Agent": "Mozilla/5.0"}, allow_redirects=True)
            r.raise_for_status()
            arq.write_bytes(r.content)
            print(f"  baixado {len(r.content) / 1e6:.1f} MB -> {arq.name}")
            return r.content
        except Exception as e:
            ultimo = e
            time.sleep(2 * t)
    raise RuntimeError(f"falha ao baixar {src}: {ultimo}")


def listar_fontes(fontes: list[str] | None = None, pasta: str = PASTA_PDFS) -> list[str]:
    fontes = list(FONTES if fontes is None else fontes)
    nomes = {arquivo_da_fonte(u, pasta).name for u in fontes if _e_link(u)}
    locais = [str(p) for p in sorted(Path(pasta).glob("*.pdf")) if p.name not in nomes]
    return list(dict.fromkeys(fontes + locais))


def ingerir(con=None, fontes: list[str] | None = None, pasta: str = PASTA_PDFS) -> dict:
    legado = _legado()
    Path(legado.DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    Path(pasta).mkdir(parents=True, exist_ok=True)
    con = con or legado.connect()
    legado.fetch = lambda src: obter_bytes(src, pasta)
    todas = listar_fontes(fontes, pasta)
    erros = []
    for src in todas:
        try:
            legado.ingest(con, src)
        except Exception as e:
            erros.append((src, str(e)))
            print(f"! erro em {src[-60:]}: {e}")
    con.commit()
    return {
        "fontes": len(todas),
        "documentos": con.execute("SELECT COUNT(*) FROM documents").fetchone()[0],
        "trechos": con.execute("SELECT COUNT(*) FROM chunks WHERE tipo != 'indice'").fetchone()[0],
        "erros": erros,
    }
