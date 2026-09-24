"""
downloader.py
Baixa o vídeo do YouTube em qualidade adequada para corte (mp4, até 1080p)
usando yt-dlp.

O YouTube muda com frequência a forma como libera o download dos vídeos, o
que às vezes causa erros como "HTTP 403 Forbidden" mesmo com o yt-dlp
atualizado. Para reduzir a chance disso travar o pipeline, tentamos o
download com algumas estratégias diferentes (clientes de player distintos)
antes de desistir.
"""
import os
import yt_dlp

# Cada item é o(s) "player_client" que o yt-dlp deve simular ao pedir os
# dados do vídeo pro YouTube. Se um bloquear (403), tentamos o próximo.
_ESTRATEGIAS_CLIENTE = [
    ["android"],
    ["ios"],
    ["web"],
    ["tv_embedded"],
]


def _tentar_download(url: str, pasta_saida: str, player_client: list):
    ydl_opts = {
        "format": "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": os.path.join(pasta_saida, "%(id)s.%(ext)s"),
        "merge_output_format": "mp4",
        "quiet": False,
        "noplaylist": True,
        "extractor_args": {"youtube": {"player_client": player_client}},
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        # IMPORTANTE: calcular o caminho aqui dentro, com essa mesma instância
        # (que tem o outtmpl/pasta corretos configurados). Criar uma instância
        # nova do YoutubeDL() em outro lugar usaria as opções padrão da lib,
        # gerando um caminho errado (bug corrigido).
        caminho = ydl.prepare_filename(info)
        return info, caminho


def baixar_video(url: str, pasta_saida: str = "downloads"):
    """
    Baixa o vídeo do YouTube e retorna (caminho_do_arquivo, titulo).
    Tenta algumas estratégias diferentes antes de desistir, para contornar
    bloqueios temporários do tipo "HTTP 403 Forbidden".
    """
    os.makedirs(pasta_saida, exist_ok=True)

    info = None
    caminho = None
    ultimo_erro = None

    for i, cliente in enumerate(_ESTRATEGIAS_CLIENTE, start=1):
        try:
            if i > 1:
                print(f"[..] Tentando estratégia alternativa de download ({', '.join(cliente)})...")
            info, caminho = _tentar_download(url, pasta_saida, cliente)
            break
        except yt_dlp.utils.DownloadError as e:
            ultimo_erro = e
            print(f"[AVISO] Falha com o cliente {cliente}: {e}")
            continue

    if info is None:
        raise RuntimeError(
            "Não foi possível baixar o vídeo com nenhuma estratégia disponível. "
            "Rode 'pip install -U yt-dlp' para garantir a versão mais recente e tente de novo. "
            f"Último erro: {ultimo_erro}"
        )

    # Garante extensão .mp4 (o merge pode trocar a extensão original)
    base, _ = os.path.splitext(caminho)
    caminho_mp4 = base + ".mp4"
    if os.path.exists(caminho_mp4):
        caminho = caminho_mp4

    if not os.path.exists(caminho):
        raise RuntimeError(
            f"O download terminou mas o arquivo esperado não foi encontrado em '{caminho}'. "
            "Verifique a pasta 'downloads/' manualmente."
        )

    titulo = info.get("title", "video")
    print(f"[OK] Vídeo baixado: {titulo} -> {caminho}")
    return caminho, titulo
