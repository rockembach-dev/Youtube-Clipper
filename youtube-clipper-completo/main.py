"""
main.py
Pipeline completo: YouTube -> transcrição -> análise estratégica de virais -> cortes.

Uso:
    python main.py "https://www.youtube.com/watch?v=XXXXXXXX"

Opções:
    --modelo-whisper small|base|medium|large-v3   (padrão: small)
    --qtd-cortes N                                (padrão: 12)
    --horizontal                                  (gera cortes no formato original, sem verticalizar)
    --idioma pt                                   (força idioma da transcrição)
    --analise local|api                           (padrão: local, gratuito)
    --layout preenchido|blur                      (padrão: preenchido)
    --sem-legenda                                 (desativa a legenda dinâmica queimada no vídeo)
    --paralelo N                                  (quantos clipes cortar ao mesmo tempo; padrão: automático)
    --rapido                                      (atalho: modelo 'base' + preset de corte mais veloz,
                                                    recomendado para vídeos longos tipo podcasts de 1h+)
    --lote                                        (tenta o pipeline em lote do faster-whisper, mais
                                                    rápido em teoria mas experimental — desativado por
                                                    padrão porque pode travar/crashar em alguns Windows)
    --sem-marca-dagua                              (desativa a logo do canal no canto superior direito)
    --handle @usuario                              (texto do @ mostrado no canto inferior esquerdo;
                                                    padrão: @cortes.do.rock)
    --sem-handle                                   (desativa o @ da conta no vídeo)
"""
import argparse
import json
import os

from downloader import baixar_video
from transcriber import transcrever, formatar_transcricao_para_analise
from analyzer_free import analisar_transcricao_local
from cutter import cortar_video
from postagem import gerar_legenda_post
from utils import slugificar


def main():
    parser = argparse.ArgumentParser(description="Gerador automático de cortes virais de vídeos do YouTube.")
    parser.add_argument("url", help="Link do vídeo do YouTube")
    parser.add_argument("--modelo-whisper", default="small")
    parser.add_argument("--qtd-cortes", type=int, default=12)
    parser.add_argument("--horizontal", action="store_true", help="Não verticalizar os cortes")
    parser.add_argument("--idioma", default=None)
    parser.add_argument(
        "--analise", choices=["local", "api"], default="local",
        help="'local' = gratuito, baseado em heurísticas de texto (padrão). "
             "'api' = usa o Claude para uma análise de conteúdo mais precisa (requer ANTHROPIC_API_KEY).",
    )
    parser.add_argument(
        "--layout", choices=["preenchido", "blur"], default="preenchido",
        help="'preenchido' = zoom/crop preenchendo a tela toda (padrão, mais 'cheio'). "
             "'blur' = vídeo original inteiro, com fundo desfocado nas bordas.",
    )
    parser.add_argument(
        "--sem-legenda", action="store_true",
        help="Desativa a legenda dinâmica queimada no vídeo (por padrão, vem ativada).",
    )
    parser.add_argument(
        "--paralelo", type=int, default=None,
        help="Quantos clipes cortar ao mesmo tempo (padrão: automático, baseado nos núcleos da CPU).",
    )
    parser.add_argument(
        "--rapido", action="store_true",
        help="Prioriza velocidade: usa o modelo Whisper 'base' (se --modelo-whisper não for "
             "informado) e um preset de corte mais veloz. Recomendado para vídeos longos.",
    )
    parser.add_argument(
        "--lote", action="store_true",
        help="Tenta o pipeline em lote (BatchedInferencePipeline) do faster-whisper. "
             "Mais rápido em teoria, mas experimental: se falhar, cai automaticamente "
             "para o modo padrão. Desativado por padrão.",
    )
    parser.add_argument(
        "--sem-marca-dagua", action="store_true",
        help="Desativa a logo do canal no canto superior direito dos clipes.",
    )
    parser.add_argument(
        "--handle", default="@cortes.do.rock",
        help="Texto do @ da conta, mostrado semi-transparente no canto inferior esquerdo.",
    )
    parser.add_argument(
        "--sem-handle", action="store_true",
        help="Desativa o @ da conta no vídeo.",
    )
    args = parser.parse_args()

    modelo_whisper = args.modelo_whisper
    preset_corte = "veryfast"
    if args.rapido:
        if args.modelo_whisper == "small":  # só troca se o usuário não escolheu outro modelo manualmente
            modelo_whisper = "base"
        preset_corte = "ultrafast"
        print("[INFO] Modo --rapido ativado: modelo Whisper 'base' + corte em preset 'ultrafast'.")

    print("=" * 60)
    print("PIPELINE DE CORTES VIRAIS")
    print("=" * 60)

    # 1. Download
    caminho_video, titulo = baixar_video(args.url)

    # Cada vídeo processado ganha sua própria subpasta dentro de "clipes/",
    # pra ficar organizado na hora de ir postando (ex: clipes/nome-do-video/01_...mp4)
    pasta_video = os.path.join("clipes", slugificar(titulo))
    os.makedirs(pasta_video, exist_ok=True)
    print(f"[INFO] Saída deste vídeo: {pasta_video}/")

    # 2. Transcrição
    segmentos, palavras = transcrever(
        caminho_video, modelo=modelo_whisper, idioma=args.idioma, usar_batch=args.lote,
    )
    transcricao_txt = formatar_transcricao_para_analise(segmentos)

    # salva a transcrição bruta, útil para revisar/depurar
    caminho_transcricao = os.path.join(pasta_video, "transcricao.txt")
    with open(caminho_transcricao, "w", encoding="utf-8") as f:
        f.write(transcricao_txt)

    # 3. Análise estratégica: local (gratuita) ou via API do Claude
    if args.analise == "api":
        from analyzer import analisar_transcricao  # import tardio: só exige a lib/chave se for usada
        cortes = analisar_transcricao(transcricao_txt, quantidade_cortes=args.qtd_cortes)
    else:
        cortes = analisar_transcricao_local(segmentos, quantidade_cortes=args.qtd_cortes)

    if not cortes:
        print("[AVISO] Nenhum corte válido foi identificado. Verifique 'transcricao.txt'.")
        return

    # 4. Corte dos vídeos
    gerados = cortar_video(
        caminho_video, cortes,
        pasta_saida=pasta_video,
        formato_vertical=not args.horizontal,
        layout=args.layout,
        palavras=palavras,
        legendas=not args.sem_legenda,
        paralelo=args.paralelo,
        preset=preset_corte,
        marca_dagua=not args.sem_marca_dagua,
        handle=None if args.sem_handle else args.handle,
    )

    # 5. Relatório final
    relatorio = {
        "video_original": titulo,
        "url": args.url,
        "cortes": [
            {
                "arquivo": g["arquivo"],
                "titulo": g["titulo"],
                "inicio": g["inicio_seg"],
                "fim": g["fim_seg"],
                "duracao_seg": round(g["fim_seg"] - g["inicio_seg"], 1),
                "gancho": g["gancho"],
                "motivo": g["motivo"],
                "plataformas": g["plataformas"],
                "legenda_sugerida": gerar_legenda_post(g, i),
            }
            for i, g in enumerate(gerados)
        ],
    }
    caminho_relatorio = os.path.join(pasta_video, "relatorio_cortes.json")
    with open(caminho_relatorio, "w", encoding="utf-8") as f:
        json.dump(relatorio, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print(f"CONCLUÍDO: {len(gerados)} clipes gerados a partir de '{titulo}'")
    print(f"Tudo salvo em: {pasta_video}/")
    print("=" * 60)


if __name__ == "__main__":
    main()
