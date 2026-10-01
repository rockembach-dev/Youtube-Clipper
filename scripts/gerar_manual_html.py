"""
scripts/gerar_manual_html.py

Mantém Instruções/manual.html (o guia visual para quem USA o programa,
sem interface própria) sincronizado com o código. Diferente da documentação
técnica em docs/*.md, este script só roda quando arquivos que afetam a forma
de uso (ex: main.py, que define os parâmetros de linha de comando) mudam.
"""
import os
import subprocess
import sys
from pathlib import Path

from google import genai

MODELO = "gemini-3.5-flash-lite"
CAMINHO_MANUAL = Path("Instruções/manual.html")

# Arquivos que, se mudarem, podem afetar o que o usuário final vê/usa.
# Ajuste essa lista conforme o projeto crescer.
ARQUIVOS_RELEVANTES = ["main.py", "README.md"]

ARVORE_VAZIA = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


def git_log(formato: str) -> str:
    r = subprocess.run(["git", "log", "-1", f"--pretty={formato}"], capture_output=True, text=True)
    return r.stdout.strip()


def obter_commit_base() -> str:
    before = os.environ.get("BEFORE_SHA", "").strip()
    if before and before != "0" * 40:
        v = subprocess.run(["git", "cat-file", "-e", f"{before}^{{commit}}"], capture_output=True)
        if v.returncode == 0:
            return before
    r = subprocess.run(["git", "rev-parse", "HEAD~1"], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ARVORE_VAZIA


def arquivos_relevantes_alterados(base: str) -> list[str]:
    r = subprocess.run(["git", "diff", "--name-only", base, "HEAD"], capture_output=True, text=True, check=True)
    alterados = set(r.stdout.splitlines())
    return [f for f in ARQUIVOS_RELEVANTES if f in alterados and Path(f).exists()]


def obter_diff(base: str, arquivo: str) -> str:
    r = subprocess.run(["git", "diff", base, "HEAD", "--", arquivo], capture_output=True, text=True, check=True)
    return r.stdout


def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[ERRO] GEMINI_API_KEY não encontrada.", file=sys.stderr)
        sys.exit(1)

    base = obter_commit_base()
    alterados = arquivos_relevantes_alterados(base)
    if not alterados:
        print("[--] Nenhum arquivo relevante para o manual do usuário foi alterado.")
        return

    print(f"[..] Arquivos relevantes alterados: {alterados}")

    diffs = "\n\n".join(f"## Diff de {a}\n```diff\n{obter_diff(base, a)}\n```" for a in alterados)
    codigos = "\n\n".join(f"## Conteúdo atual de {a}\n```\n{Path(a).read_text(encoding='utf-8')}\n```" for a in alterados)

    manual_atual = CAMINHO_MANUAL.read_text(encoding="utf-8") if CAMINHO_MANUAL.exists() else None

    info_commit = (
        f"Hash: {git_log('%h')} | Autor: {git_log('%an')} | "
        f"Data: {git_log('%ad')} | Mensagem: {git_log('%s')}"
    )

    if manual_atual:
        instrucao = (
            "Você mantém um manual de uso em HTML, voltado para usuários finais "
            "(pessoas que vão RODAR o programa, não ler o código). Abaixo está o "
            "HTML atual do manual, o(s) diff(s) de código que motivaram esta "
            "atualização e o conteúdo completo dos arquivos relevantes. "
            "Atualize APENAS o que de fato mudou para quem usa o programa "
            "(ex: um novo parâmetro de linha de comando, um valor padrão "
            "diferente, um passo de instalação que mudou). "
            "PRESERVE rigorosamente o design existente: mesma paleta de cores, "
            "tipografia, estrutura de seções, classes CSS e tom de escrita — "
            "não reescreva o visual do zero. Se nada relevante para o usuário "
            "final mudou (ex: o diff é só uma refatoração interna), devolva o "
            "HTML exatamente como está. "
            f"Informações do commit atual: {info_commit}. "
            "Responda APENAS com o HTML completo final, sem comentários extras, "
            "sem markdown, sem ```."
        )
        contexto = f"\n\n## HTML atual do manual\n{manual_atual}"
    else:
        instrucao = (
            "Crie um manual de uso em HTML completo, autocontido (CSS inline, "
            "sem dependências locais), voltado para usuários finais não técnicos "
            "que vão rodar este programa de linha de comando. Use um design "
            "limpo e profissional, com blocos estilizados de terminal mostrando "
            "comandos reais. Baseie todo o conteúdo apenas no que os arquivos "
            "abaixo realmente mostram. "
            f"Informações do commit atual: {info_commit}. "
            "Responda APENAS com o HTML completo, sem comentários extras, sem ```."
        )
        contexto = ""

    prompt = f"{instrucao}\n\n{diffs}\n\n{codigos}{contexto}"

    client = genai.Client(api_key=api_key)
    resposta = client.models.generate_content(model=MODELO, contents=prompt)
    html_final = resposta.text.strip()

    CAMINHO_MANUAL.parent.mkdir(exist_ok=True)
    CAMINHO_MANUAL.write_text(html_final, encoding="utf-8")
    print(f"[OK] {CAMINHO_MANUAL} atualizado.")


if __name__ == "__main__":
    main()
