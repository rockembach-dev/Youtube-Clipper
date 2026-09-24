"""
cutter.py
Corta os trechos identificados usando ffmpeg. Gera a versão vertical 9:16
(1080x1920) pronta para TikTok/Reels/Shorts, com legendas dinâmicas e a logo
do canal (marca d'água) queimadas no vídeo.

Dois modos de layout vertical:
  - "preenchido" (padrão): dá zoom e corta as laterais para preencher todo o
    quadro vertical, sem barras — visual mais "cheio" e comum em cortes virais.
    Ideal quando o que importa está sempre no centro do quadro (uma pessoa falando).
  - "blur": mantém o vídeo original inteiro, centralizado, com o fundo
    desfocado preenchendo as bordas. Mais seguro quando há conteúdo importante
    nas laterais (ex: duas pessoas em uma entrevista lado a lado).

Os clipes são cortados em PARALELO (vários processos ffmpeg ao mesmo tempo),
aproveitando os múltiplos núcleos da CPU em vez de cortar um de cada vez.
"""
import os
import subprocess
import tempfile
import concurrent.futures

from captions import gerar_ass_para_corte, escapar_caminho_ffmpeg, RODAPE_DURACAO
from utils import slugificar

# --- Marca d'água (logo do canal) --------------------------------------------
CAMINHO_LOGO_PADRAO = os.path.join("assets", "logo.png")
LARGURA_LOGO_PROPORCAO = 0.19   # ~19% da largura do vídeo final (era 12%)
MARGEM_LOGO = 28                # distância da logo até as bordas (em px)
OPACIDADE_LOGO = 0.97           # 1.0 = totalmente opaca

# --- Handle da conta (@usuario) ----------------------------------------------
HANDLE_PADRAO = "@cortes.do.rock"

# --- Faixa vermelha de abertura (rodapé) --------------------------------------
ALTURA_FAIXA_RODAPE = 220       # altura da faixa vermelha, em px (canvas 1080x1920)
COR_FAIXA_RODAPE = "0xE8231F"   # vermelho vibrante, formato hex do ffmpeg (RRGGBB)


def _obter_dimensoes_video(caminho_video: str):
    """Descobre largura/altura do vídeo original via ffprobe."""
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0",
        caminho_video,
    ]
    resultado = subprocess.run(cmd, capture_output=True, text=True)
    largura_str, altura_str = resultado.stdout.strip().split("x")
    return int(largura_str), int(altura_str)


def _calcular_layout_blur(caminho_video: str, largura_canvas: int = 1080, altura_canvas: int = 1920):
    """
    No layout 'blur', o vídeo original fica inteiro e centralizado, com fundo
    desfocado nas bordas. A altura exata do vídeo dentro do quadro depende da
    proporção de cada vídeo (16:9, 4:3, etc), então calculamos aqui pra saber
    onde ele termina — e assim colar a faixa vermelha certinho embaixo dele,
    em vez de deixá-la solta lá no fundo desfocado.

    Retorna (altura_video_no_quadro, y_topo_do_video, y_base_do_video).
    """
    largura_original, altura_original = _obter_dimensoes_video(caminho_video)
    altura_video = round(largura_canvas * altura_original / largura_original)
    if altura_video % 2 != 0:  # altura par, exigência comum de codecs de vídeo
        altura_video += 1
    altura_video = min(altura_video, altura_canvas)  # nunca maior que o próprio quadro
    y_topo = (altura_canvas - altura_video) // 2
    y_base = y_topo + altura_video
    return altura_video, y_topo, y_base


def _filtro_layout(formato_vertical: bool, layout: str, info_blur: tuple = None) -> str:
    if not formato_vertical:
        return "[0:v]copy[v]"

    if layout == "preenchido":
        # Zoom + crop central: preenche 1080x1920 inteiro, sem barras.
        return (
            "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920[v]"
        )

    # layout == "blur": vídeo original inteiro, centralizado, fundo desfocado.
    # Usa a altura/posição exatas calculadas em _calcular_layout_blur (em vez da
    # expressão automática "(H-h)/2" do ffmpeg) para garantir que a faixa
    # vermelha, desenhada separadamente, fique exatamente colada na base do vídeo.
    altura_video, y_topo, _ = info_blur
    return (
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,gblur=sigma=20[bg];"
        f"[0:v]scale=1080:{altura_video}[fg];"
        f"[bg][fg]overlay=0:{y_topo}[v]"
    )


def _cortar_um_clipe(indice: int, total: int, corte: dict, caminho_video: str,
                      pasta_saida: str, pasta_temp: str, formato_vertical: bool,
                      layout: str, palavras: list, legendas: bool, preset: str, crf: int,
                      marca_dagua: bool, caminho_logo: str, handle: str, info_blur: tuple):
    """Corta um único clipe. Roda em paralelo (uma chamada por clipe)."""
    duracao = corte["fim_seg"] - corte["inicio_seg"]
    nome_base = f"{indice:02d}_{slugificar(corte['titulo'])}"
    caminho_saida = os.path.join(pasta_saida, f"{nome_base}.mp4")
    largura_saida = 1080 if formato_vertical else 1920

    filtro = _filtro_layout(formato_vertical, layout, info_blur)
    rotulo_video_final = "v"

    usar_logo = marca_dagua and caminho_logo and os.path.isfile(caminho_logo)
    entradas_extra = []

    if usar_logo:
        largura_logo = max(int(largura_saida * LARGURA_LOGO_PROPORCAO), 40)
        entradas_extra = ["-loop", "1", "-i", caminho_logo]
        filtro += (
            f";[1:v]scale={largura_logo}:-1,format=rgba,"
            f"colorchannelmixer=aa={OPACIDADE_LOGO}[wm];"
            f"[v][wm]overlay=W-w-{MARGEM_LOGO}:{MARGEM_LOGO}[vmarca]"
        )
        rotulo_video_final = "vmarca"

    # Faixa vermelha de largura total, com o gancho identificado, nos primeiros
    # segundos do clipe (o retângulo é desenhado aqui; o texto por cima dele
    # vem do arquivo .ass gerado logo abaixo).
    # No layout "blur", cola a faixa logo abaixo do vídeo (não no fundo do
    # quadro); no "preenchido", o vídeo já ocupa o quadro todo, então tanto
    # faz — fica na base mesmo.
    margem_rodape_extra = 0
    if legendas and corte.get("gancho"):
        duracao_faixa = min(RODAPE_DURACAO, duracao)
        if formato_vertical and layout == "blur" and info_blur:
            _, _, y_base_video = info_blur
            y_faixa = min(y_base_video, 1920 - ALTURA_FAIXA_RODAPE)
            margem_rodape_extra = 1920 - (y_faixa + ALTURA_FAIXA_RODAPE)
        else:
            y_faixa = "ih-" + str(ALTURA_FAIXA_RODAPE)
            margem_rodape_extra = 0
        filtro += (
            f";[{rotulo_video_final}]drawbox="
            f"x=0:y={y_faixa}:w=iw:h={ALTURA_FAIXA_RODAPE}:"
            f"color={COR_FAIXA_RODAPE}@1.0:t=fill:"
            f"enable='between(t,0,{duracao_faixa})'[vfaixa]"
        )
        rotulo_video_final = "vfaixa"

    caminho_ass = None
    if legendas and (palavras or corte.get("gancho") or handle):
        caminho_ass_destino = os.path.join(pasta_temp, f"{nome_base}.ass")
        caminho_ass = gerar_ass_para_corte(
            palavras or [], corte["inicio_seg"], corte["fim_seg"], caminho_ass_destino,
            largura=largura_saida,
            altura=1920 if formato_vertical else 1080,
            texto_headline=corte.get("gancho"),
            texto_handle=handle,
            margem_rodape_extra=margem_rodape_extra,
        )

    if caminho_ass:
        caminho_escapado = escapar_caminho_ffmpeg(caminho_ass)
        filtro += f";[{rotulo_video_final}]ass='{caminho_escapado}'[vlegendado]"
        rotulo_video_final = "vlegendado"

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(corte["inicio_seg"]),
        "-i", caminho_video,
        *entradas_extra,
        "-filter_complex", filtro,
        "-map", f"[{rotulo_video_final}]", "-map", "0:a?",
        "-t", str(duracao),
        "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
        "-c:a", "aac", "-b:a", "192k",
        caminho_saida,
    ]

    print(f"[..] Cortando trecho {indice}/{total}: {corte['titulo']} "
          f"({corte['inicio_seg']:.0f}s -> {corte['fim_seg']:.0f}s)"
          f"{' [com legenda]' if caminho_ass else ''}"
          f"{' [com marca d\u2019água]' if usar_logo else ''}")

    resultado = subprocess.run(cmd, capture_output=True, text=True)
    if resultado.returncode != 0:
        print(f"[ERRO] Falha ao cortar '{corte['titulo']}'. Detalhes do ffmpeg:")
        print(resultado.stderr[-2000:])  # mostra só o final, costuma ter a causa do erro
        return None

    print(f"[OK] Trecho {indice}/{total} concluído: {nome_base}.mp4")
    return {**corte, "arquivo": caminho_saida}


def cortar_video(caminho_video: str, cortes: list, pasta_saida: str = "clipes",
                  formato_vertical: bool = True, layout: str = "preenchido",
                  palavras: list = None, legendas: bool = True,
                  paralelo: int = None, preset: str = "veryfast", crf: int = 21,
                  marca_dagua: bool = True, caminho_logo: str = CAMINHO_LOGO_PADRAO,
                  handle: str = HANDLE_PADRAO):
    """
    Gera um arquivo .mp4 para cada corte identificado, em paralelo.

    layout: "preenchido" ou "blur" (só tem efeito se formato_vertical=True)
    palavras: lista de palavras com timestamps (vinda de transcriber.transcrever),
              necessária para gerar as legendas dinâmicas
    legendas: se True e `palavras` foi informado, queima legendas no vídeo
    paralelo: quantos clipes cortar ao mesmo tempo. Padrão: usa os núcleos de
              CPU disponíveis (até um teto de 4, para não sobrecarregar a máquina
              nem competir demais por I/O de disco).
    preset: preset de velocidade do libx264 (ultrafast/veryfast/fast/medium...).
            Presets mais rápidos geram arquivos um pouco maiores, com qualidade
            ligeiramente inferior — "veryfast" é um bom equilíbrio.
    crf: qualidade do vídeo (menor = melhor qualidade e arquivo maior). 18-23 é
         a faixa recomendada para redes sociais.
    marca_dagua: se True, queima a logo do canal no canto superior direito.
    caminho_logo: caminho do arquivo de imagem da logo (PNG com fundo
                  transparente funciona melhor). Se o arquivo não existir,
                  a marca d'água é simplesmente pulada sem dar erro.
    handle: texto do @ da conta, mostrado semi-transparente no canto inferior
            esquerdo durante todo o clipe. Passe None ou "" para desativar.
    """
    os.makedirs(pasta_saida, exist_ok=True)
    pasta_temp = tempfile.mkdtemp(prefix="legendas_")

    if marca_dagua and not (caminho_logo and os.path.isfile(caminho_logo)):
        print(f"[AVISO] Marca d'água ativada, mas o arquivo '{caminho_logo}' não foi encontrado. "
              f"Os clipes serão gerados sem a logo.")

    if paralelo is None:
        paralelo = min(4, os.cpu_count() or 2)

    # No layout "blur", calcula uma única vez onde o vídeo termina dentro do
    # quadro (é sempre o mesmo vídeo fonte para todos os cortes) — evita
    # rodar o ffprobe 12 vezes à toa, uma por clipe.
    info_blur = None
    if formato_vertical and layout == "blur":
        info_blur = _calcular_layout_blur(caminho_video)

    print(f"[..] Cortando {len(cortes)} clipes em paralelo ({paralelo} de cada vez)...")

    gerados = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=paralelo) as executor:
        futuros = [
            executor.submit(
                _cortar_um_clipe, i, len(cortes), c, caminho_video, pasta_saida,
                pasta_temp, formato_vertical, layout, palavras, legendas, preset, crf,
                marca_dagua, caminho_logo, handle, info_blur,
            )
            for i, c in enumerate(cortes, start=1)
        ]
        for futuro in concurrent.futures.as_completed(futuros):
            resultado = futuro.result()
            if resultado:
                gerados.append(resultado)

    # os clipes podem terminar fora de ordem por causa do paralelismo;
    # reordena cronologicamente pelo início no vídeo original
    gerados.sort(key=lambda g: g["inicio_seg"])

    print(f"[OK] {len(gerados)} clipes gerados em '{pasta_saida}/'.")
    return gerados
