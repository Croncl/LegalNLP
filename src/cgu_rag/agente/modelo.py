"""Modelo de chat do agente (LangChain) apontando para o servidor local (Ollama, API /v1).

Mantem a politica de sigilo (D-10): com SIGILO=sigiloso so aceita endpoint local ou de rede privada.
"""
from __future__ import annotations

from langchain_openai import ChatOpenAI

from ..config import settings
from ..llm_local import PoliticaSigiloViolada, endpoint_local


def criar_modelo(model: str | None = None, base_url: str | None = None, sigilo: str | None = None,
                 temperature: float = 0.1, **kw) -> ChatOpenAI:
    base_url = base_url or settings.llm_base_url
    if (sigilo or settings.sigilo) == "sigiloso" and not endpoint_local(base_url):
        raise PoliticaSigiloViolada(f"SIGILO=sigiloso exige endpoint local/rede privada; recebido: {base_url}")
    return ChatOpenAI(model=model or settings.llm_model, base_url=base_url, api_key=settings.llm_api_key,
                      temperature=temperature, **kw)
