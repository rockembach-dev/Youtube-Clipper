"""
analyzer_free.py
Versão GRATUITA do analisador — não usa nenhuma API paga. Identifica trechos
prováveis de viralizar usando heurísticas de texto sobre a transcrição:
palavras-gancho, pontuação de impacto, números/estatísticas, marcadores de
humor/surpresa e densidade de fala.

É bem menos preciso que a análise feita pelo Claude (analyzer.py), porque não
"entende" o conteúdo de verdade — só reconhece padrões de superfície no texto.
Serve para testar o pipeline todo sem custo, antes de migrar para a versão com IA.
"""
import re

# Palavras/expressões que costumam indicar um "gancho" ou pico de valor em PT-BR.
# Ajuste esta lista livremente conforme o nicho do canal.
PALAVRAS_GANCHO = [
    "você não vai acreditar", "ninguém te conta", "segredo", "verdade",
    "erro que", "isso mudou", "descobri", "aprendi", "grande sacada",
    "olha só", "presta atenção", "atenção", "importante", "cuidado",
    "a real é", "gente", "juro", "sério", "inacreditável", "impressionante",
    "revelou", "revelação", "chocante", "polêmico", "polêmica", "controverso",
    "dica", "truque", "método", "passo a passo", "nunca", "sempre",
    "ninguém fala", "pouca gente sabe", "número", "estatística", "dados mostram",
    "por que", "como assim", "resultado", "consegui", "mudou minha vida",
]

MARCADORES_HUMOR = ["kkk", "haha", "rs ", " rs", "engraçado", "hilário", "morri"]

PONTUACAO_IMPACTO = re.compile(r"[!?]")
NUMEROS = re.compile(r"\b\d+([.,]\d+)?\s*(%|por cento|mil|milh(ão|ões)|reais|r\$)?\b", re.IGNORECASE)

DURACAO_MIN = 30
DURACAO_MAX = 120
DURACOES_ALVO = [30, 45, 60, 90, 120]  # janelas testadas a partir de cada ponto de início


def _pontuar_texto(texto: str) -> float:
    """
    Dá uma pontuação heurística a um trecho de texto (quanto maior, mais 'viral').
    Ganchos que aparecem logo na ABERTURA do trecho (primeiras ~10 palavras) valem
    bem mais, porque são o que realmente prende a atenção nos primeiros segundos
    — um gancho no meio ou no fim do trecho não impede a pessoa de sair do vídeo antes.
    """
    texto_lower = texto.lower()
    palavras_lista = texto_lower.split()
    abertura = " ".join(palavras_lista[:10])

    pontos = 0.0

    for palavra in PALAVRAS_GANCHO:
        if palavra in abertura:
            pontos += 4.0  # gancho logo no início: peso bem maior
        elif palavra in texto_lower:
            pontos += 1.0  # gancho em qualquer outro ponto: ainda soma, mas bem menos

    for marcador in MARCADORES_HUMOR:
        if marcador in texto_lower:
            pontos += 1.5

    pontos += len(PONTUACAO_IMPACTO.findall(texto)) * 0.5
    pontos += len(NUMEROS.findall(texto)) * 1.0

    # normaliza um pouco pelo tamanho do texto pra não favorecer só trechos longos
    palavras_totais = max(len(palavras_lista), 1)
    pontos = pontos / (palavras_totais ** 0.3)

    return pontos


def _gerar_janelas(segmentos: list) -> list:
    """
    Gera janelas candidatas (início, fim, texto, pontuação) percorrendo os
    segmentos da transcrição e testando durações de 30s a 120s a partir de
    cada ponto de início.
    """
    janelas = []
    n = len(segmentos)

    for i in range(n):
        inicio = segmentos[i]["inicio"]
        for duracao_alvo in DURACOES_ALVO:
            fim_alvo = inicio + duracao_alvo
            j = i
            texto_partes = []
            while j < n and segmentos[j]["inicio"] < fim_alvo:
                texto_partes.append(segmentos[j]["texto"])
                j += 1
            if j == i:
                continue
            fim_real = segmentos[j - 1]["fim"]
            duracao_real = fim_real - inicio
            if duracao_real < DURACAO_MIN or duracao_real > DURACAO_MAX:
                continue

            texto = " ".join(texto_partes).strip()
            if not texto:
                continue

            pontuacao = _pontuar_texto(texto)
            janelas.append({
                "inicio_seg": inicio,
                "fim_seg": fim_real,
                "texto": texto,
                "pontuacao": pontuacao,
            })

    return janelas


def _sobrepoe(a: dict, b: dict, margem: float = 5.0) -> bool:
    return not (a["fim_seg"] + margem <= b["inicio_seg"] or b["fim_seg"] + margem <= a["inicio_seg"])


def _titulo_a_partir_do_texto(texto: str) -> str:
    palavras = texto.strip().split()
    titulo = " ".join(palavras[:8])
    if len(palavras) > 8:
        titulo += "..."
    return titulo.capitalize()


def _gancho_a_partir_do_texto(texto: str) -> str:
    partes = re.split(r"(?<=[.!?])\s+", texto.strip())
    return partes[0] if partes else texto[:80]


def analisar_transcricao_local(segmentos: list, quantidade_cortes: int = 6) -> list:
    """
    Versão gratuita: não chama nenhuma API. Retorna a mesma estrutura que a
    versão com Claude (analyzer.py), para ser usada de forma intercambiável
    no main.py.
    """
    print("[..] Analisando trechos localmente (modo GRATUITO, sem API)...")

    janelas = _gerar_janelas(segmentos)
    if not janelas:
        print("[AVISO] Nenhuma janela candidata encontrada (vídeo muito curto?).")
        return []

    janelas.sort(key=lambda w: w["pontuacao"], reverse=True)

    escolhidas = []
    for janela in janelas:
        if any(_sobrepoe(janela, e) for e in escolhidas):
            continue
        escolhidas.append(janela)
        if len(escolhidas) >= quantidade_cortes:
            break

    # ordena por ordem cronológica no vídeo final, fica mais fácil de revisar
    escolhidas.sort(key=lambda w: w["inicio_seg"])

    cortes = []
    for e in escolhidas:
        cortes.append({
            "inicio_seg": e["inicio_seg"],
            "fim_seg": e["fim_seg"],
            "titulo": _titulo_a_partir_do_texto(e["texto"]),
            "motivo": (
                f"Selecionado por heurística local (pontuação {e['pontuacao']:.2f}) — "
                "detectou palavras-gancho, pontuação de impacto e/ou números no trecho."
            ),
            "gancho": _gancho_a_partir_do_texto(e["texto"]),
            "plataformas": ["tiktok", "instagram", "shorts"],
        })

    print(f"[OK] {len(cortes)} cortes identificados (modo gratuito).")
    return cortes
