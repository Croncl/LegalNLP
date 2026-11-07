"""Mostra o passo a passo de UM turno do agente: mensagens, chamadas de ferramenta e resultados.

Uso (na raiz do projeto, com o Ollama rodando):
  python scripts/depurar.py "Qual a multa prevista no PAR?"
  python scripts/depurar.py "Qual a multa prevista no PAR?" --modelo qwen2.5:3b
Serve para descobrir se o modelo consultou a base, com que consulta, o que a base devolveu e o que ele respondeu.
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cgu_rag.agente.ferramentas import criar_buscador, criar_ferramenta_consulta  # noqa: E402
from cgu_rag.agente.grafo import conversar, criar_grafo  # noqa: E402
from cgu_rag.agente.modelo import criar_modelo  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pergunta")
    ap.add_argument("--modelo", default=None, help="modelo do Ollama (padrao: LLM_MODEL)")
    a = ap.parse_args()
    consulta = criar_ferramenta_consulta(criar_buscador())
    modelo = criar_modelo(model=a.modelo)
    print("modelo:", modelo.model_name)
    grafo = criar_grafo(modelo, ferramentas=[consulta])
    t0 = time.time()
    _, estado = conversar(grafo, a.pergunta, "depuracao")
    print(f"\n=== passo a passo ({time.time() - t0:.0f}s) ===")
    for m in estado["messages"]:
        chamadas = [(c["name"], c["args"]) for c in getattr(m, "tool_calls", [])]
        print(f"\n[{m.type}]" + (f" CHAMOU {chamadas}" if chamadas else ""))
        if str(m.content).strip():
            print(str(m.content)[:700])
    print("\nferramentas do turno:", estado["ferramentas"] or "NENHUMA (o modelo respondeu sem consultar a base)")


if __name__ == "__main__":
    main()
