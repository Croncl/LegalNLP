
## Removidos em 05/11/2026
| Tag | Motivo | Evidencia | Espaco liberado | Como recuperar |
|---|---|---|---|---|
| jurema-7b e hf.co/mauroneto/Jurema-7B-Q4_K_M-GGUF | Nao usa a ferramenta de consulta dentro do grafo e inventa leis e artigos quando responde sem consultar | 0 de 8 perguntas consultadas no benchmark (n = 8) e 0 de 2 no teste manual; ver docs/RESULTADOS.md e o diario (R7b) | 4,7 GB | `ollama pull hf.co/mauroneto/Jurema-7B-Q4_K_M-GGUF:latest` e `ollama create jurema-7b -f models/Modelfile.jurema-7b` |
| SparkLLM/Spark-X2.6-4B:latest (BF16) | Nao usado: os testes usam a versao Q8_0 | inventario de 05/11/2026 | 8,2 GB | `ollama pull SparkLLM/Spark-X2.6-4B:latest` |
| Spark-X2.6-4B-Q8:latest | Alias duplicado de SparkLLM/Spark-X2.6-4B:q8_0 (mesmo ID 2d3a7d5f159f) | ollama list | 0 (os arquivos sao compartilhados) | `ollama cp SparkLLM/Spark-X2.6-4B:q8_0 Spark-X2.6-4B-Q8` |

## Candidatos a comparar
| Modelo | Situacao | Observacao |
|---|---|---|
| SparkLLM/Spark-X2.6-4B:q8_0 | instalado | ponto de partida |
| qwen2.5:3b | instalado | rapido; 75% de consulta no benchmark preliminar |
| qwen2.5:7b | a baixar | o teste de 30/10 foi invalido (modelo nao instalado) |
| NVIDIA Nemotron 3.5 Bolt E4B (Q4_K_M, repositorio oficial da NVIDIA) | a baixar | 8B no total e 4B efetivos, base Gemma 4, 64K de contexto, ferramentas em varias rodadas, raciocinio configuravel, licenca OpenMDW-1.1; lancado em 23/10/2026 (fontes secundarias; conferir o model card). NVIDIA recomenda temperatura 1,0; o projeto usa 0,1 para todos |
| qwen3.8:27b (Q4_K_M) | instalado | referencia de qualidade, fora do uso interativo |

Fora da comparacao: Qwen3.8-27B FP8 (exige GPU grande e vLLM ou Transformers; nao roda no Ollama em CPU, e o Q4_K_M ja esta instalado).
