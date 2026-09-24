"""
analyzer.py
Envia a transcrição (com timestamps) para o Claude analisar estrategicamente
e devolver os melhores trechos para cortes de redes sociais.
"""
import os
import json
import re
from anthropic import Anthropic

MODELO_CLAUDE = "claude-sonnet-4-6"

PROMPT_SISTEMA = """Você é um estrategista de conteúdo especializado em cortes virais para \
TikTok, Instagram Reels e YouTube Shorts. Você analisa transcrições de vídeos longos \
(com timestamps) e identifica os melhores trechos para virar cortes curtos e autônomos.

Critérios para um bom corte:
- Tem um GANCHO forte nos primeiros 2-3 segundos (pergunta intrigante, afirmação polêmica, \
promessa de resultado, frase de impacto).
- Funciona sozinho, sem precisar de contexto do resto do vídeo.
- Contém um pico de valor: humor, revelação, dado surpreendente, história emocional, \
conselho prático, virada de raciocínio ou controvérsia.
- Tem começo, meio e fim natural dentro da janela de tempo (não corta no meio de uma ideia).
- Duração entre 30 segundos e 2 minutos.

Responda APENAS com um JSON válido (sem markdown, sem texto antes ou depois), no formato:
{
  "cortes": [
    {
      "inicio": "MM:SS",
      "fim": "MM:SS",
      "titulo": "título curto e chamativo para o corte",
      "motivo": "por que esse trecho tem potencial viral (1-2 frases)",
      "gancho": "a frase/momento exato que prende a atenção nos primeiros segundos",
      "plataformas_sugeridas": ["tiktok", "instagram", "shorts"]
    }
  ]
}
"""


def _mmss_para_segundos(t: str) -> float:
    partes = t.strip().split(":")
    partes = [float(p) for p in partes]
    while len(partes) < 3:
        partes.insert(0, 0)
    h, m, s = partes
    return h * 3600 + m * 60 + s


def analisar_transcricao(transcricao_formatada: str, quantidade_cortes: int = 6) -> list:
    """
    Chama a API da Anthropic para identificar os melhores trechos.
    Retorna lista de dicts: inicio_seg, fim_seg, titulo, motivo, gancho, plataformas.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Defina a variável de ambiente ANTHROPIC_API_KEY com sua chave da API da Anthropic."
        )

    client = Anthropic(api_key=api_key)

    prompt_usuario = f"""Aqui está a transcrição do vídeo com timestamps:

{transcricao_formatada}

Identifique os {quantidade_cortes} melhores trechos para cortes virais, seguindo os critérios \
do sistema. Priorize variedade (não escolha só trechos parecidos) e garanta que cada corte \
tenha entre 30 segundos e 2 minutos."""

    resposta = client.messages.create(
        model=MODELO_CLAUDE,
        max_tokens=4000,
        system=PROMPT_SISTEMA,
        messages=[{"role": "user", "content": prompt_usuario}],
    )

    texto = "".join(bloco.text for bloco in resposta.content if bloco.type == "text")

    # Remove possíveis cercas de markdown, por segurança
    texto = re.sub(r"^```json\s*|\s*```$", "", texto.strip())

    dados = json.loads(texto)
    cortes = []
    for c in dados.get("cortes", []):
        inicio_seg = _mmss_para_segundos(c["inicio"])
        fim_seg = _mmss_para_segundos(c["fim"])
        duracao = fim_seg - inicio_seg
        if duracao < 25 or duracao > 130:
            # descarta cortes fora da faixa pedida (com pequena margem)
            continue
        cortes.append({
            "inicio_seg": inicio_seg,
            "fim_seg": fim_seg,
            "titulo": c.get("titulo", "corte"),
            "motivo": c.get("motivo", ""),
            "gancho": c.get("gancho", ""),
            "plataformas": c.get("plataformas_sugeridas", ["tiktok", "instagram", "shorts"]),
        })

    print(f"[OK] {len(cortes)} cortes identificados pela análise estratégica.")
    return cortes
