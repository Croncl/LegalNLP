"""Conversa pelo terminal com o agente (grafo + RAG agentico), sem interface.

Uso (na raiz do projeto, com o Ollama rodando):  python scripts/chat.py
Comandos: /nova (nova conversa) e /sair
"""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cgu_rag.agente.ferramentas import criar_buscador, criar_ferramenta_consulta  # noqa: E402
from cgu_rag.agente.grafo import conversar, criar_grafo  # noqa: E402
from cgu_rag.agente.modelo import criar_modelo  # noqa: E402


def main():
    consulta = criar_ferramenta_consulta(criar_buscador())
    grafo = criar_grafo(criar_modelo(), ferramentas=[consulta])
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
        resposta, estado = conversar(grafo, texto, thread)
        for c in estado.get("ferramentas", []):
            print(f"  [ferramenta] {c['nome']}: {c['args']}")
        print("assistente>", resposta)


if __name__ == "__main__":
    main()
