"""Mede velocidade do LLM local com um prompt de ~3000 tokens (o tamanho de um contexto de RAG).

Uso:  python scripts/medir_llm.py [--chars 12000] [--max-tokens 128]
Resultado salvo em results/medicao_llm.json. Guarde o resultado de cada configuracao (quantizacao,
num_ctx, numero de threads) para decidir onde cada tarefa roda.
"""
import argparse
import json
import platform
from pathlib import Path

from cgu_rag.config import settings
from cgu_rag.llm_local import LLMLocal

BASE = ("A Controladoria-Geral da Uniao realiza atividades de correicao para apurar responsabilidades "
        "administrativas, conforme as normas aplicaveis ao processo administrativo disciplinar. ")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chars", type=int, default=12000, help="tamanho do prompt (12000 car. ~ 3000 tokens)")
    ap.add_argument("--max-tokens", type=int, default=128)
    a = ap.parse_args()
    prompt = (BASE * (a.chars // len(BASE) + 1))[: a.chars] + "\n\nResuma o texto acima em duas frases."
    llm = LLMLocal()
    llm.medir("Diga ola.", max_tokens=8)  # aquecimento: carrega o modelo na memoria
    r = llm.medir(prompt, max_tokens=a.max_tokens)
    r.update({"modelo": settings.llm_model, "endpoint": settings.llm_base_url,
              "prompt_chars": a.chars, "maquina": platform.node(), "cpu": platform.processor()})
    print(json.dumps(r, ensure_ascii=False, indent=2))
    out = Path("results/medicao_llm.json")
    historico = json.loads(out.read_text()) if out.exists() else []
    historico.append(r)
    out.write_text(json.dumps(historico, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
