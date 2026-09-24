"""
postagem.py
Gera uma sugestão de legenda + hashtags para postar cada corte, pronta pra
copiar e colar no TikTok/Instagram/Shorts. Sem custo de API — usa templates
simples a partir dos dados já identificados na análise (título e gancho).
"""

HASHTAGS_BASE = ["#cortes", "#viral", "#fy", "#fyp", "#foryou", "#reels", "#shorts"]

CHAMADAS_PARA_ACAO = [
    "Comenta aqui o que você acha 👇",
    "Segue pra mais cortes como esse 🔥",
    "Manda pra alguém que precisa ver isso",
    "Salva esse vídeo pra assistir depois",
]


def gerar_legenda_post(corte: dict, indice: int) -> str:
    """
    Monta uma legenda pronta pra postar, combinando o gancho identificado
    com uma chamada para ação e hashtags. Varia a CTA por índice só pra não
    ficar repetitivo entre os 12 cortes.
    """
    gancho = corte.get("gancho", "").strip()
    cta = CHAMADAS_PARA_ACAO[indice % len(CHAMADAS_PARA_ACAO)]
    hashtags = " ".join(HASHTAGS_BASE)

    partes = []
    if gancho:
        partes.append(gancho if gancho.endswith((".", "!", "?")) else gancho + "...")
    partes.append(cta)
    partes.append(hashtags)

    return "\n\n".join(partes)
