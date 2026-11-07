"""Testa se o modelo local aceita chamada de ferramentas (tool calling) pelo Ollama.

Uso (na raiz do projeto, com o Ollama rodando):
  python scripts/testar_tools.py                  # testa o modelo de LLM_MODEL (jurema-7b)
  python scripts/testar_tools.py --modelo qwen2.5:3b
  $env:LLM_PENSAR="false"; python scripts/testar_tools.py --modelo qwen3.8:27b   (desliga o raciocinio)
Resultado esperado de um modelo bom: chama a ferramenta na 1a pergunta e NAO chama na 2a.
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from langchain_core.tools import tool  # noqa: E402

from cgu_rag.agente.modelo import criar_modelo  # noqa: E402


@tool
def consultar_base(consulta: str) -> str:
    """Busca trechos nos normativos da CGU sobre PAD e PAR. Use para perguntas sobre prazos, ritos e regras."""
    return "(teste)"


PERGUNTAS = [
    ("DEVE chamar", "Qual e o prazo para instauracao do PAD apos o conhecimento da irregularidade?"),
    ("NAO deve chamar", "Ola, tudo bem? Apresente-se em uma frase."),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", default=None)
    a = ap.parse_args()
    modelo = criar_modelo(model=a.modelo)
    print("modelo:", modelo.model_name)
    com_ferramentas = modelo.bind_tools([consultar_base])
    for esperado, pergunta in PERGUNTAS:
        t0 = time.time()
        try:
            r = com_ferramentas.invoke(pergunta)
        except Exception as e:
            print(f"ERRO ({type(e).__name__}): {str(e)[:250]}")
            print("Provavel causa: o modelo nao tem template de ferramentas no Ollama (ver D-14).")
            return 1
        chamou = [c["name"] for c in r.tool_calls]
        tokens = (r.usage_metadata or {}).get("output_tokens", "?")  # muitos tokens numa resposta curta = raciocinio ligado
        print(f"[{esperado}] chamou={chamou or 'nenhuma'} | {time.time() - t0:.0f}s | tokens={tokens} | texto={str(r.content)[:70]!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
