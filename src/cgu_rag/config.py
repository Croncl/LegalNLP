"""Configuracao central. Le variaveis de ambiente (e .env, se existir) uma unica vez.

IMPORTANTE: este modulo define RAG_DB e RAG_EMB_MODEL ANTES de o modulo legado ser importado,
porque o legado le essas variaveis no momento do import.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _carregar_dotenv(caminho: Path = Path(".env")) -> None:
    if not caminho.exists():
        return
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        os.environ.setdefault(chave.strip(), valor.strip())


_carregar_dotenv()
os.environ.setdefault("RAG_DB", "data/rag_cgu.db")
os.environ.setdefault("RAG_EMB_MODEL", "intfloat/multilingual-e5-small")


@dataclass(frozen=True)
class Settings:
    llm_base_url: str = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
    llm_model: str = os.getenv("LLM_MODEL", "jurema-7b")
    llm_api_key: str = os.getenv("LLM_API_KEY", "ollama")
    sigilo: str = os.getenv("SIGILO", "sigiloso")  # "publico" | "sigiloso"
    db_path: str = os.environ["RAG_DB"]
    emb_model: str = os.environ["RAG_EMB_MODEL"]


settings = Settings()
