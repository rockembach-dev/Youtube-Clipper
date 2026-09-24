"""
captions.py
Gera legendas no formato .ass (Advanced SubStation Alpha) para os cortes:

  1. Faixa de abertura ("gancho no rodapé"): uma faixa vermelha sólida,
     largura total da tela, com um texto extraído da transcrição (o gancho
     identificado na análise), fixa nos primeiros segundos do clipe.
     Estilo usado por muitos canais de corte (ex: vídeos de carros, fatos
     curiosos): funciona como uma "capa" que prende atenção mesmo com o som
     desligado. A faixa em si (o retângulo vermelho) é desenhada pelo
     cutter.py via ffmpeg; aqui só geramos o texto por cima dela.
  2. Legenda dinâmica palavra-a-palavra (estilo canal de cortes), com a
     palavra falada no momento destacada em outra cor. Só começa a aparecer
     DEPOIS que a faixa de abertura sai da tela, pra não competir visualmente.
  3. Handle da conta (@usuario): texto pequeno, no canto superior direito,
     logo abaixo da logo do canal (que é desenhada pelo cutter.py). Fica
     visível do início ao fim do clipe, com opacidade reduzida (mais discreto,
     mas ainda legível). Serve tanto pra converter quem assistiu em seguidor
     quanto como proteção contra republicação sem crédito.
"""
import os
import textwrap

# --- Aparência da legenda dinâmica (ajuste livremente) ----------------------
FONTE = "Anton"
TAMANHO_FONTE = 100
COR_TEXTO = "&H00FFFFFF"       # branco (formato ASS: &HAABBGGRR, sem alpha = &H00)
COR_DESTAQUE = "&H0000FFFF"    # amarelo (BGR: 00=B, FF=G, FF=R -> amarelo)
COR_BORDA = "&H00000000"       # contorno preto
ESPESSURA_BORDA = 5
MARGEM_INFERIOR = 350          # distância da legenda até a base do vídeo (em px, no canvas 1080x1920)
MAX_PALAVRAS_POR_BLOCO = 3
DURACAO_MAX_BLOCO = 2.2        # segundos
ESCALA_PALAVRA_ATIVA = 140     # % de tamanho da palavra sendo falada (100 = tamanho normal)

# --- Aparência da faixa de abertura (rodapé) ---------------------------------
RODAPE_FONTE = "Anton"
RODAPE_TAMANHO_FONTE = 100
RODAPE_COR_TEXTO = "&H00FFFFFF"        # branco 
RODAPE_COR_BORDA = "&H00000000"        # contorno preto (reforça leitura sobre o vermelho)
RODAPE_ESPESSURA_BORDA = 3
RODAPE_MARGEM_INFERIOR = 12             # ajuda a centralizar o texto dentro da faixa (ver ALTURA_FAIXA_RODAPE no cutter.py)
RODAPE_MARGEM_LATERAL = 55
RODAPE_MAX_CARACTERES_POR_LINHA = 28
RODAPE_DURACAO = 3.2                   # segundos que a faixa fica na tela

# --- Aparência do handle da conta (@usuario) ---------------------------------
# Fica logo abaixo da logo, no canto superior direito (por isso usa as mesmas
# proporções da logo definidas no cutter.py, pra alinhar certinho por baixo dela).
HANDLE_FONTE = "Arial Black"
HANDLE_TAMANHO_FONTE = 34
HANDLE_COR_TEXTO = "&H55FFFFFF"     # branco, mais apagado (alpha 0x55 de 0xFF; 00=opaco, FF=invisível)
HANDLE_COR_BORDA = "&H60000000"     # contorno preto, também mais apagado
HANDLE_ESPESSURA_BORDA = 3
LOGO_LARGURA_PROPORCAO = 0.19       # deve bater com LARGURA_LOGO_PROPORCAO no cutter.py
LOGO_MARGEM = 28                    # deve bater com MARGEM_LOGO no cutter.py
HANDLE_GAP_ABAIXO_LOGO = 16         # distância entre a base da logo e o texto


def calcular_duracao_rodape(duracao_corte: float, tem_rodape: bool) -> float:
    """Quanto tempo a faixa de abertura fica na tela (0 se não houver gancho)."""
    if not tem_rodape:
        return 0.0
    return min(RODAPE_DURACAO, duracao_corte)


def _formatar_tempo_ass(segundos: float) -> str:
    if segundos < 0:
        segundos = 0
    h = int(segundos // 3600)
    m = int((segundos % 3600) // 60)
    s = segundos % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _agrupar_palavras(palavras: list) -> list:
    """Agrupa palavras em pequenos blocos (2-3 palavras) para exibir por vez na tela."""
    blocos = []
    bloco_atual = []
    inicio_bloco = None

    for p in palavras:
        if not bloco_atual:
            bloco_atual = [p]
            inicio_bloco = p["inicio"]
            continue

        duracao_se_adicionar = p["fim"] - inicio_bloco
        if len(bloco_atual) >= MAX_PALAVRAS_POR_BLOCO or duracao_se_adicionar > DURACAO_MAX_BLOCO:
            blocos.append(bloco_atual)
            bloco_atual = [p]
            inicio_bloco = p["inicio"]
        else:
            bloco_atual.append(p)

    if bloco_atual:
        blocos.append(bloco_atual)

    return blocos


def _texto_do_bloco(bloco: list, indice_ativo: int) -> str:
    partes = []
    for i, p in enumerate(bloco):
        palavra = p["palavra"].strip().upper()
        if i == indice_ativo:
            # cor de destaque + aumenta o tamanho da palavra sendo falada no momento
            partes.append(
                f"{{\\c{COR_DESTAQUE}&\\fscx{ESCALA_PALAVRA_ATIVA}\\fscy{ESCALA_PALAVRA_ATIVA}}}"
                f"{palavra}"
                f"{{\\c{COR_TEXTO}&\\fscx100\\fscy100}}"
            )
        else:
            partes.append(palavra)
    return " ".join(partes)


def _escapar_texto_ass(texto: str) -> str:
    return texto.replace("{", "(").replace("}", ")")


def _texto_rodape(texto: str) -> str:
    """Quebra o texto da faixa em linhas curtas (\\N = quebra de linha no ASS)."""
    texto = _escapar_texto_ass(texto.strip().upper())
    linhas = textwrap.wrap(texto, width=RODAPE_MAX_CARACTERES_POR_LINHA, max_lines=2,
                            placeholder="...")
    return "\\N".join(linhas)


def gerar_ass_para_corte(palavras: list, inicio_corte: float, fim_corte: float,
                          caminho_saida: str, largura: int = 1080, altura: int = 1920,
                          texto_headline: str = None, texto_handle: str = None,
                          margem_rodape_extra: int = 0):
    """
    Filtra as palavras dentro da janela [inicio_corte, fim_corte], desloca os
    timestamps para começar em 0 (tempo relativo ao clipe) e escreve um arquivo
    .ass com:
      - o texto da faixa de abertura (rodapé), se `texto_headline` for informado
        (a faixa vermelha em si é desenhada pelo cutter.py; aqui só o texto)
      - a legenda dinâmica, palavra a palavra — só a partir do fim da faixa
      - o handle da conta (@usuario), se `texto_handle` for informado — também
        só a partir do fim da faixa, pra não sobrepor visualmente

    margem_rodape_extra: distância entre a base do quadro e a base da faixa
        vermelha (0 quando a faixa fica colada na base do quadro, como no
        layout "preenchido"; maior que 0 no layout "blur", onde a faixa fica
        colada no vídeo, que normalmente termina antes da base do quadro).
        Usado pra subir o texto junto com a faixa, e não deixá-lo pra trás.

    Retorna o caminho do arquivo gerado, ou None se não havia nada pra mostrar.
    """
    duracao_corte = fim_corte - inicio_corte
    duracao_rodape = calcular_duracao_rodape(duracao_corte, bool(texto_headline))
    margem_inferior_rodape = RODAPE_MARGEM_INFERIOR + max(margem_rodape_extra, 0)

    # margem do handle = espaço ocupado pela logo (que fica no canto superior
    # direito, desenhada pelo cutter.py) + um respiro, pra ficar coladinho embaixo dela
    margem_superior_handle = int(largura * LOGO_LARGURA_PROPORCAO) + LOGO_MARGEM + HANDLE_GAP_ABAIXO_LOGO

    palavras_do_corte = [
        {"inicio": p["inicio"] - inicio_corte, "fim": p["fim"] - inicio_corte, "palavra": p["palavra"]}
        for p in palavras
        if p["inicio"] >= inicio_corte and p["fim"] <= fim_corte + 0.05
        and (p["inicio"] - inicio_corte) >= duracao_rodape
    ]

    if not palavras_do_corte and not texto_headline and not texto_handle:
        return None

    cabecalho = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {largura}
PlayResY: {altura}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Legenda,{FONTE},{TAMANHO_FONTE},{COR_TEXTO},{COR_DESTAQUE},{COR_BORDA},&H00000000,-1,0,0,0,100,100,0,0,1,{ESPESSURA_BORDA},0,2,60,60,{MARGEM_INFERIOR},1
Style: Rodape,{RODAPE_FONTE},{RODAPE_TAMANHO_FONTE},{RODAPE_COR_TEXTO},{RODAPE_COR_TEXTO},{RODAPE_COR_BORDA},&H00000000,-1,0,0,0,100,100,0,0,1,{RODAPE_ESPESSURA_BORDA},0,2,{RODAPE_MARGEM_LATERAL},{RODAPE_MARGEM_LATERAL},{margem_inferior_rodape},1
Style: Handle,{HANDLE_FONTE},{HANDLE_TAMANHO_FONTE},{HANDLE_COR_TEXTO},{HANDLE_COR_TEXTO},{HANDLE_COR_BORDA},&H00000000,-1,0,0,0,100,100,0,0,1,{HANDLE_ESPESSURA_BORDA},0,9,{LOGO_MARGEM},{LOGO_MARGEM},{margem_superior_handle},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    linhas_eventos = []

    # --- Texto da faixa de abertura (a faixa vermelha vem do cutter.py) ---
    if texto_headline and duracao_rodape > 0:
        texto_formatado = _texto_rodape(texto_headline)
        linhas_eventos.append(
            f"Dialogue: 1,{_formatar_tempo_ass(0)},{_formatar_tempo_ass(duracao_rodape)},"
            f"Rodape,,0,0,0,,{texto_formatado}"
        )

    # --- Handle da conta (canto superior direito, do início ao fim do clipe) ---
    if texto_handle:
        texto_formatado = _escapar_texto_ass(texto_handle.strip())
        linhas_eventos.append(
            f"Dialogue: 1,{_formatar_tempo_ass(0)},{_formatar_tempo_ass(duracao_corte)},"
            f"Handle,,0,0,0,,{texto_formatado}"
        )

    # --- Legenda dinâmica palavra-a-palavra (a partir do fim da faixa) ---
    blocos = _agrupar_palavras(palavras_do_corte)
    for bloco in blocos:
        for i, palavra_ativa in enumerate(bloco):
            inicio_evento = palavra_ativa["inicio"]
            fim_evento = bloco[i + 1]["inicio"] if i + 1 < len(bloco) else palavra_ativa["fim"]
            if fim_evento <= inicio_evento:
                fim_evento = inicio_evento + 0.1
            texto = _texto_do_bloco(bloco, i)
            linha = (
                f"Dialogue: 0,{_formatar_tempo_ass(inicio_evento)},{_formatar_tempo_ass(fim_evento)},"
                f"Legenda,,0,0,0,,{texto}"
            )
            linhas_eventos.append(linha)

    with open(caminho_saida, "w", encoding="utf-8") as f:
        f.write(cabecalho)
        f.write("\n".join(linhas_eventos))

    return caminho_saida


def escapar_caminho_ffmpeg(caminho: str) -> str:
    """
    Formata um caminho de arquivo para uso dentro de um filtro do ffmpeg
    (filtergraph), que exige barras normais e escapa os dois-pontos do
    caminho (problema comum no Windows, ex: C:\\pasta\\arquivo.ass).
    """
    caminho_abs = os.path.abspath(caminho)
    caminho_abs = caminho_abs.replace("\\", "/")
    caminho_abs = caminho_abs.replace(":", "\\:")
    return caminho_abs
