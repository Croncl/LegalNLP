"""Modelo de chat do agente (LangChain) apontando para o servidor local (Ollama, API /v1).

Mantem a politica de sigilo (D-10): com SIGILO=sigiloso so aceita endpoint local ou de rede privada.
Modo de raciocinio ("thinking"): modelos como o Qwen3.8 pensam por padrao, o que no CPU multiplica o tempo.
Para desligar, use LLM_PENSAR=false (variavel de ambiente) ou criar_modelo(pensar=False).
Sem essa variavel nada muda para os demais modelos.
"""
from __future__ import annotations

import os

from langchain_openai import ChatOpenAI

from ..config import settings
from ..llm_local import PoliticaSigiloViolada, endpoint_local


def _pensar_padrao() -> bool | None:
    v = os.getenv("LLM_PENSAR", "").strip().lower()
    return None if not v else v not in ("0", "false", "nao", "no")


def criar_modelo(model: str | None = None, base_url: str | None = None, sigilo: str | None = None,
                 temperature: float = 0.1, pensar: bool | None = None, **kw) -> ChatOpenAI:
    base_url = base_url or settings.llm_base_url
    if (sigilo or settings.sigilo) == "sigiloso" and not endpoint_local(base_url):
        raise PoliticaSigiloViolada(f"SIGILO=sigiloso exige endpoint local/rede privada; recebido: {base_url}")
    pensar = _pensar_padrao() if pensar is None else pensar
    if pensar is False:  # pede ao Ollama para nao raciocinar (parametros ignorados por modelos sem esse recurso)
        kw.setdefault("reasoning_effort", "none")
        kw.setdefault("extra_body", {"think": False})
    return ChatOpenAI(model=model or settings.llm_model, base_url=base_url, api_key=settings.llm_api_key,
                      temperature=temperature, **kw)
