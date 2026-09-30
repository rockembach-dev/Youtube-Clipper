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
MODELO = "gemini-3.5-flash-lite"
PASTA_DOCS = Path("docs")

# Se seu código-fonte estiver em pastas específicas, filtre aqui.
PASTAS_MONITORADAS = []  # ex: ["youtube-clipper-completo"]

# Hash "mágico" do Git que representa uma árvore vazia — usado como base de
# comparação quando não existe nenhum commit anterior de verdade (ex: o
# primeiro push do repositório).
ARVORE_VAZIA = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


def obter_commit_base() -> str:
    """
    Decide contra qual commit comparar. Usa o SHA de antes de TODO o push
    (github.event.before), não só do último commit — assim, se alguém der
    push com vários commits de uma vez, ou se uma execução anterior tiver
    falhado no meio do caminho, nenhuma mudança fica "perdida" na comparação.
    """
    before = os.environ.get("BEFORE_SHA", "").strip()

    if before and before != "0" * 40:
        verificacao = subprocess.run(
            ["git", "cat-file", "-e", f"{before}^{{commit}}"],
            capture_output=True,
        )
        if verificacao.returncode == 0:
            return before

    # Fallback 1: tenta o commit anterior ao HEAD (caso BEFORE_SHA não
    # esteja disponível, ex: rodando localmente sem essa variável).
    resultado = subprocess.run(
        ["git", "rev-parse", "HEAD~1"], capture_output=True, text=True,
    )
    if resultado.returncode == 0:
        return resultado.stdout.strip()

    # Fallback 2: é o primeiro commit que existe no repositório — compara
    # contra a árvore vazia (ou seja, tudo no HEAD é "novo").
    return ARVORE_VAZIA


def arquivos_alterados() -> list[str]:
    base = obter_commit_base()
    resultado = subprocess.run(
        ["git", "diff", "--name-only", base, "HEAD"],
        capture_output=True, text=True, check=True,
    )
    arquivos = [f for f in resultado.stdout.splitlines() if f.endswith(".py")]
    if PASTAS_MONITORADAS:
        arquivos = [f for f in arquivos if any(f.startswith(p) for p in PASTAS_MONITORADAS)]
    return arquivos


def obter_diff(arquivo: str) -> str:
    base = obter_commit_base()
    resultado = subprocess.run(
        ["git", "diff", base, "HEAD", "--", arquivo],
        capture_output=True, text=True, check=True,
    )
    return resultado.stdout


def obter_metadados_commit() -> dict:
    """Busca dados reais do commit atual, para a IA usar em vez de inventar
    placeholders como 'YYYY-MM-DD' ou 'Desenvolvedor'."""
    def git_log(formato: str) -> str:
        resultado = subprocess.run(
            ["git", "log", "-1", f"--pretty={formato}"],
            capture_output=True, text=True,
        )
        return resultado.stdout.strip()

    return {
        "hash_curto": git_log("%h"),
        "autor": git_log("%an"),
        "data": git_log("%ad") + "",  # formato padrão do git já é legível
        "mensagem": git_log("%s"),
    }


def caminho_doc(arquivo: str) -> Path:
    nome_modulo = Path(arquivo).stem
    return PASTA_DOCS / f"{nome_modulo}.md"


def montar_prompt(arquivo: str, diff: str, codigo_atual: str, doc_antiga: str | None, metadados: dict) -> str:
    info_commit = (
        f"- Hash do commit: {metadados['hash_curto']}\n"
        f"- Autor: {metadados['autor']}\n"
        f"- Data: {metadados['data']}\n"
        f"- Mensagem do commit: {metadados['mensagem']}"
    )

    if doc_antiga:
        instrucao = (
            "Abaixo está a documentação ATUAL desse módulo, o DIFF da mudança "
            "recente e o CÓDIGO COMPLETO já atualizado. Atualize a documentação "
            "considerando apenas o que realmente mudou no comportamento/estrutura "
            "do código. Preserve seções que não foram afetadas pela mudança. "
            "Se algo foi renomeado, movido de lugar ou desativado/comentado, "
            "deixe isso explícito, incluindo se algum trecho de funcionalidade "
            "foi comentado e por isso está inativo no momento. "
            "Adicione uma linha na tabela de Histórico de mudanças no final, "
            "descrevendo especificamente o que esse diff mudou (não escreva "
            "algo genérico). Use OBRIGATORIAMENTE a data e o hash do commit "
            "reais fornecidos abaixo em 'Informações do commit atual' — nunca "
            "escreva placeholders como 'YYYY-MM-DD' ou 'Desenvolvedor'. "
            "Responda APENAS com o markdown final do documento, sem comentários extras."
        )
        contexto_doc = f"\n\n## Documentação atual\n{doc_antiga}"
    else:
        instrucao = (
            "Este módulo já existe no código, mas ainda não tinha documentação "
            "registrada até agora — não confunda isso com 'módulo recém-criado'. "
            "Gere uma documentação completa cobrindo o estado ATUAL do código "
            "(já refletindo a mudança mostrada no diff, incluindo qualquer trecho "
            "comentado/desativado por ela). Seções: Propósito, Como funciona, "
            "Dependências, Pontos de configuração (o que costuma mudar). "
            "Na tabela de Histórico de mudanças, a ÚNICA linha deve descrever "
            "especificamente a mudança real mostrada no diff acima — não escreva "
            "'implementação inicial' nem qualquer texto genérico de placeholder, "
            "a menos que o diff mostre de fato a criação do arquivo do zero. "
            "Use OBRIGATORIAMENTE a data e o hash do commit reais fornecidos "
            "abaixo em 'Informações do commit atual' — nunca escreva "
            "placeholders como 'YYYY-MM-DD' ou 'Desenvolvedor'. "
            "Responda APENAS com o markdown final do documento, sem comentários extras."
        )
        contexto_doc = ""

    return f"""{instrucao}

## Arquivo: {arquivo}

## Informações do commit atual
{info_commit}

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


def gerar_ou_atualizar_doc(client: genai.Client, arquivo: str, metadados: dict) -> None:
    print(f"[..] Processando {arquivo}")

    diff = obter_diff(arquivo)
    if not diff.strip():
        print(f"[--] Sem diff relevante para {arquivo}, pulando.")
        return

    codigo_atual = Path(arquivo).read_text(encoding="utf-8")
    caminho = caminho_doc(arquivo)
    doc_antiga = caminho.read_text(encoding="utf-8") if caminho.exists() else None

    prompt = montar_prompt(arquivo, diff, codigo_atual, doc_antiga, metadados)

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
    metadados = obter_metadados_commit()

    arquivos = arquivos_alterados()
    if not arquivos:
        print("[--] Nenhum arquivo .py relevante alterado neste commit.")
        return

    for arquivo in arquivos:
        try:
            gerar_ou_atualizar_doc(client, arquivo, metadados)
        except Exception as e:
            print(f"[ERRO] Falha ao processar {arquivo}: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
