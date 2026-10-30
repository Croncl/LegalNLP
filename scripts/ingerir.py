"""Ingere os PDFs (links de fontes.py + PDFs em data/pdfs/) no banco SQLite.

Uso (na raiz do projeto):  python scripts/ingerir.py
E idempotente: PDFs ja ingeridos e sem mudanca sao ignorados.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cgu_rag.ingestao import ingerir  # noqa: E402


def main() -> int:
    r = ingerir()
    print(f"\nfontes: {r['fontes']} | documentos no banco: {r['documentos']} | trechos: {r['trechos']} | erros: {len(r['erros'])}")
    for src, msg in r["erros"]:
        print(" -", src[-60:], "->", msg)
    return 1 if r["erros"] else 0


if __name__ == "__main__":
    sys.exit(main())
