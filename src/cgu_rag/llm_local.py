"""Cliente de LLM para endpoint compativel com OpenAI (Ollama, llama.cpp, vLLM).

Politica de sigilo (versao minima do gateway da secao 14 do documento):
- SIGILO=sigiloso: so aceita endpoint em localhost ou rede privada; caso contrario FALHA (fail-closed).
- Nunca ha fallback automatico para outro provedor.
"""
from __future__ import annotations

import ipaddress
import time
from urllib.parse import urlparse

from .config import settings


class PoliticaSigiloViolada(RuntimeError):
    pass


def endpoint_local(url: str) -> bool:
    host = urlparse(url).hostname or ""
    if host in ("localhost", "::1"):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False  # nome DNS desconhecido: nao presumir que e local
    return ip.is_loopback or ip.is_private


class LLMLocal:
    def __init__(self, base_url: str | None = None, model: str | None = None,
                 api_key: str | None = None, sigilo: str | None = None):
        self.base_url = base_url or settings.llm_base_url
        self.model = model or settings.llm_model
        self.api_key = api_key or settings.llm_api_key
        self.sigilo = sigilo or settings.sigilo
        if self.sigilo == "sigiloso" and not endpoint_local(self.base_url):
            raise PoliticaSigiloViolada(
                f"SIGILO=sigiloso exige endpoint local/rede privada; recebido: {self.base_url}")
        from openai import OpenAI  # import tardio: testes nao exigem o pacote
        self._client = OpenAI(base_url=self.base_url, api_key=self.api_key)

    def chat(self, mensagens: list[dict], max_tokens: int = 700, temperature: float = 0.1) -> str:
        r = self._client.chat.completions.create(
            model=self.model, messages=mensagens, max_tokens=max_tokens, temperature=temperature)
        return r.choices[0].message.content or ""

    def medir(self, prompt: str, max_tokens: int = 128) -> dict:
        """Mede tempo ate o primeiro token e velocidade de geracao (aproximada por blocos de stream)."""
        t0 = time.perf_counter()
        t_primeiro = None
        n = 0
        fluxo = self._client.chat.completions.create(
            model=self.model, messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens, temperature=0.0, stream=True)
        for parte in fluxo:
            if parte.choices and parte.choices[0].delta.content:
                if t_primeiro is None:
                    t_primeiro = time.perf_counter()
                n += 1
        t1 = time.perf_counter()
        if t_primeiro is None:
            raise RuntimeError("o servidor nao devolveu nenhum token")
        gen = max(t1 - t_primeiro, 1e-9)
        return {"ttft_s": round(t_primeiro - t0, 2), "blocos_gerados": n,
                "blocos_por_s": round(n / gen, 2), "total_s": round(t1 - t0, 2)}
