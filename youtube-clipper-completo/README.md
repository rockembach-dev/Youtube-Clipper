# YouTube Clipper — Cortes Virais Automáticos

Pipeline que pega um link do YouTube, transcreve o vídeo, usa a IA da Anthropic (Claude)
para identificar os trechos com maior potencial viral, e gera automaticamente os cortes
(30s a 2min) já no formato vertical 9:16, prontos para TikTok, Instagram Reels e YouTube Shorts.

## Como funciona

1. **Download** (`downloader.py`) — baixa o vídeo com `yt-dlp`.
2. **Transcrição** (`transcriber.py`) — transcreve o áudio com timestamps usando `faster-whisper`
   (roda localmente, sem custo de API).
3. **Análise estratégica** (`analyzer.py`) — envia a transcrição para o Claude, que identifica
   os melhores trechos considerando: gancho nos primeiros segundos, pico de valor (humor,
   revelação, dado surpreendente, virada de raciocínio), e se o trecho funciona sozinho.
4. **Corte** (`cutter.py`) — usa `ffmpeg` para cortar cada trecho e opcionalmente
   reformatar para vertical 1080x1920 (com fundo desfocado preenchendo as bordas).

## Instalação

```bash
# 1. Instale o ffmpeg (necessário para download e corte)
#    macOS:
brew install ffmpeg
#    Ubuntu/Debian:
sudo apt install ffmpeg

# 2. Crie um ambiente virtual (recomendado)
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 3. Instale as dependências Python
pip install -r requirements.txt
```

## Configuração

Você precisa de uma chave de API da Anthropic (console.anthropic.com):

```bash
export ANTHROPIC_API_KEY="sua-chave-aqui"     # Linux/macOS
setx ANTHROPIC_API_KEY "sua-chave-aqui"       # Windows
```

## Uso

```bash
python main.py "https://www.youtube.com/watch?v=XXXXXXXX"
```

Opções:

| Flag | Descrição | Padrão |
|---|---|---|
| `--modelo-whisper` | `tiny`, `base`, `small`, `medium`, `large-v3` (maior = mais preciso, mais lento) | `small` |
| `--qtd-cortes` | Quantos cortes tentar gerar | `6` |
| `--horizontal` | Mantém o formato original em vez de verticalizar | desligado |
| `--idioma` | Força o idioma da transcrição (ex: `pt`) | detecção automática |

Exemplo com mais cortes e modelo mais preciso:

```bash
python main.py "https://youtu.be/XXXXXXXX" --qtd-cortes 8 --modelo-whisper medium
```

## Saída

- `clipes/` — os vídeos cortados, nomeados por ordem e título (`01_titulo-do-corte.mp4`, ...)
- `transcricao.txt` — transcrição completa com timestamps (útil para revisar)
- `relatorio_cortes.json` — detalhes de cada corte: horário, gancho usado, motivo da escolha
  e plataformas sugeridas

## Dicas

- Vídeos de podcast/entrevista/aula tendem a gerar os melhores cortes (há mais "picos" de
  conteúdo isolável). Vídeos muito editados/musicais funcionam pior com este pipeline.
- Se os cortes vierem cortando frases no meio, teste um modelo Whisper maior
  (`medium` ou `large-v3`) para timestamps mais precisos.
- O corte vertical usa um fundo desfocado do próprio vídeo. Se quiser fundo sólido/personalizado,
  ajuste o filtro `gblur` em `cutter.py`.
- Legendas automáticas (burn-in) não estão incluídas aqui, mas dá pra evoluir o pipeline
  usando os timestamps da transcrição — posso montar isso também se quiser.
