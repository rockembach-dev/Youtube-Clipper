"""
scripts/atualizar_docs.py  (versão Gemini - tier gratuito)

Roda dentro do GitHub Actions a cada push. Para cada arquivo .py alterado no
último commit, gera ou atualiza a documentação correspondente em docs/,
usando a API gratuita do Gemini (Google AI Studio) para interpretar o
código e o diff.

Como conseguir a chave gratuita: https://aistudio.google.com/apikey
(não precisa cartão de crédito para o tier gratuito)
"""
import os
import subprocess
import sys
from pathlib import Path

from google import genai

# Modelo leve e com tier gratuito generoso - bom para testes.
# Alternativas gratuitas: "gemini-2.0-flash-lite", "gemini-2.5-flash"
MODELO = "gemini-2.0-flash-lite"
PASTA_DOCS = Path("docs")

# Se seu código-fonte estiver em pastas específicas, filtre aqui.
PASTAS_MONITORADAS = []  # ex: ["youtube-clipper-completo"]


def arquivos_alterados() -> list[str]:
    resultado = subprocess.run(
        ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
        capture_output=True, text=True, check=True,
    )
    arquivos = [f for f in resultado.stdout.splitlines() if f.endswith(".py")]
    if PASTAS_MONITORADAS:
        arquivos = [f for f in arquivos if any(f.startswith(p) for p in PASTAS_MONITORADAS)]
    return arquivos


def obter_diff(arquivo: str) -> str:
    resultado = subprocess.run(
        ["git", "diff", "HEAD~1", "HEAD", "--", arquivo],
        capture_output=True, text=True, check=True,
    )
    return resultado.stdout


def caminho_doc(arquivo: str) -> Path:
    nome_modulo = Path(arquivo).stem
    return PASTA_DOCS / f"{nome_modulo}.md"


def montar_prompt(arquivo: str, diff: str, codigo_atual: str, doc_antiga: str | None) -> str:
    if doc_antiga:
        instrucao = (
            "Abaixo está a documentação ATUAL desse módulo, o DIFF da mudança "
            "recente e o CÓDIGO COMPLETO já atualizado. Atualize a documentação "
            "considerando apenas o que realmente mudou no comportamento/estrutura "
            "do código. Preserve seções que não foram afetadas pela mudança. "
            "Se algo foi renomeado ou movido de lugar, deixe isso explícito. "
            "Adicione uma linha na tabela de Histórico de mudanças no final. "
            "Responda APENAS com o markdown final do documento, sem comentários extras."
        )
        contexto_doc = f"\n\n## Documentação atual\n{doc_antiga}"
    else:
        instrucao = (
            "Este módulo ainda não tem documentação. Gere uma documentação "
            "completa em markdown com as seções: Propósito, Como funciona, "
            "Dependências, Pontos de configuração (o que costuma mudar), e uma "
            "tabela de Histórico de mudanças com uma única linha inicial. "
            "Responda APENAS com o markdown final do documento, sem comentários extras."
        )
        contexto_doc = ""

    return f"""{instrucao}

## Arquivo: {arquivo}

## Diff da mudança
```diff
{diff}
```

## Código completo atual do arquivo
```python
{codigo_atual}
```
{contexto_doc}
"""


def gerar_ou_atualizar_doc(client: genai.Client, arquivo: str) -> None:
    print(f"[..] Processando {arquivo}")

    diff = obter_diff(arquivo)
    if not diff.strip():
        print(f"[--] Sem diff relevante para {arquivo}, pulando.")
        return

    codigo_atual = Path(arquivo).read_text(encoding="utf-8")
    caminho = caminho_doc(arquivo)
    doc_antiga = caminho.read_text(encoding="utf-8") if caminho.exists() else None

    prompt = montar_prompt(arquivo, diff, codigo_atual, doc_antiga)

    resposta = client.models.generate_content(model=MODELO, contents=prompt)
    texto_doc = resposta.text

    PASTA_DOCS.mkdir(exist_ok=True)
    caminho.write_text(texto_doc, encoding="utf-8")
    print(f"[OK] Documentação {'atualizada' if doc_antiga else 'criada'}: {caminho}")


def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[ERRO] Variável GEMINI_API_KEY não encontrada.", file=sys.stderr)
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    arquivos = arquivos_alterados()
    if not arquivos:
        print("[--] Nenhum arquivo .py relevante alterado neste commit.")
        return

    for arquivo in arquivos:
        try:
            gerar_ou_atualizar_doc(client, arquivo)
        except Exception as e:
            print(f"[ERRO] Falha ao processar {arquivo}: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
