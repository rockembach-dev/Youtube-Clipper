"""
transcriber.py
Transcreve o áudio do vídeo com timestamps por segmento usando faster-whisper
(roda localmente, sem custo de API).

Otimizações de velocidade:
  - usa todos os núcleos de CPU disponíveis (cpu_threads) — sempre ativo, estável.
  - pipeline em lote (BatchedInferencePipeline) — OPCIONAL, desativado por padrão.
    Em teoria acelera bastante, mas é um recurso mais novo do faster-whisper que
    pode falhar silenciosamente (crash nativo, sem traceback Python) em algumas
    combinações de Windows/CPU. Só ative com --lote se quiser testar.
"""
import os
import sys
from faster_whisper import WhisperModel

try:
    from faster_whisper import BatchedInferencePipeline
    _TEM_PIPELINE_BATCH = True
except ImportError:
    _TEM_PIPELINE_BATCH = False


def _print_flush(msg: str):
    """Print com flush imediato, para o progresso aparecer na hora no terminal
    (sem isso, em alguns terminais o texto só aparece em blocos, dando a
    falsa impressão de que o programa travou)."""
    print(msg, flush=True)


def transcrever(caminho_video: str, modelo: str = "small", idioma: str = None,
                 usar_batch: bool = False, batch_size: int = 16):
    """
    Retorna uma tupla (segmentos, palavras):
      - segmentos: [{"inicio": float, "fim": float, "texto": str}, ...]  (por frase/trecho)
      - palavras:  [{"inicio": float, "fim": float, "palavra": str}, ...] (por palavra individual,
                    usado para gerar as legendas dinâmicas estilo "corte")

    modelo: "tiny", "base", "small", "medium", "large-v3"
            (modelos maiores = mais precisos e mais lentos. Para vídeos longos,
            "base" costuma dar um ótimo equilíbrio velocidade/qualidade)
    idioma: força um idioma (ex: "pt"). Se None, detecta automaticamente.
    usar_batch: tenta usar o pipeline em lote do faster-whisper (mais rápido em
                teoria, mas experimental). Se falhar por qualquer motivo, cai
                automaticamente para o modo padrão (estável).
    batch_size: quantos trechos de áudio processar simultaneamente no modo batch.
    """
    cpu_threads = os.cpu_count() or 4
    _print_flush(f"[..] Carregando modelo Whisper '{modelo}' usando {cpu_threads} threads de CPU "
                 f"(pode demorar na 1ª vez)...")
    model = WhisperModel(modelo, device="cpu", compute_type="int8", cpu_threads=cpu_threads)

    segments = None
    info = None

    if usar_batch and _TEM_PIPELINE_BATCH:
        try:
            _print_flush(f"[..] Transcrevendo áudio (modo em lote, batch_size={batch_size})...")
            pipeline = BatchedInferencePipeline(model=model)
            segments, info = pipeline.transcribe(
                caminho_video,
                language=idioma,
                word_timestamps=True,
                batch_size=batch_size,
            )
        except Exception as e:
            _print_flush(f"[AVISO] Pipeline em lote falhou ({e}). Caindo para o modo padrão (estável).")
            segments = None

    if segments is None:
        if usar_batch and not _TEM_PIPELINE_BATCH:
            _print_flush("[AVISO] Pipeline em lote não disponível nesta versão do faster-whisper. "
                         "Usando modo padrão.")
        _print_flush("[..] Transcrevendo áudio (isso pode levar vários minutos em vídeos longos)...")
        segments, info = model.transcribe(
            caminho_video,
            language=idioma,
            vad_filter=True,  # remove silêncios longos
            word_timestamps=True,
        )

    resultado = []
    palavras = []
    for idx, seg in enumerate(segments, start=1):
        resultado.append({
            "inicio": round(seg.start, 2),
            "fim": round(seg.end, 2),
            "texto": seg.text.strip(),
        })
        if seg.words:
            for w in seg.words:
                palavra_limpa = w.word.strip()
                if palavra_limpa:
                    palavras.append({
                        "inicio": round(w.start, 2),
                        "fim": round(w.end, 2),
                        "palavra": palavra_limpa,
                    })

        # mostra progresso a cada ~20 segmentos, pra ficar claro que está avançando
        if idx % 20 == 0:
            m, s = divmod(int(seg.end), 60)
            _print_flush(f"    ... transcrito até {m:02d}:{s:02d} do vídeo ({idx} trechos)")

    _print_flush(f"[OK] Transcrição concluída ({len(resultado)} segmentos, "
                 f"{len(palavras)} palavras, idioma detectado: {info.language}).")
    return resultado, palavras


def formatar_transcricao_para_analise(segmentos) -> str:
    """
    Formata a transcrição em texto legível com timestamps, para enviar à IA.
    Formato: [MM:SS] texto
    """
    linhas = []
    for s in segmentos:
        m, sec = divmod(int(s["inicio"]), 60)
        linhas.append(f"[{m:02d}:{sec:02d}] {s['texto']}")
    return "\n".join(linhas)
