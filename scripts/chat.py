"""Conversa pelo terminal com o grafo (teste do R6, sem interface).

Uso (na raiz do projeto, com o Ollama rodando):  python scripts/chat.py
Comandos: /nova (nova conversa) e /sair
"""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cgu_rag.agente.grafo import conversar, criar_grafo  # noqa: E402
from cgu_rag.llm_local import LLMLocal  # noqa: E402


def main():
    grafo = criar_grafo(LLMLocal())
    thread = uuid.uuid4().hex[:8]
    print(f"Conversa {thread}. Comandos: /nova, /sair")
    while True:
        try:
            texto = input("\nvoce> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if texto == "/sair":
            break
        if texto == "/nova":
            thread = uuid.uuid4().hex[:8]
            print(f"nova conversa: {thread}")
            continue
        resposta, _ = conversar(grafo, texto, thread)
        print("assistente>", resposta)


if __name__ == "__main__":
    main()
