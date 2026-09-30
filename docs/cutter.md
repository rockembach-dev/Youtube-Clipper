# Documentação do Módulo: `cutter.py`

## Propósito
O módulo `cutter.py` é responsável por realizar o corte físico dos trechos identificados em vídeos utilizando o FFmpeg. Ele gera versões verticais otimizadas (9:16, resolução 1080x1920) prontas para plataformas como TikTok, Instagram Reels e YouTube Shorts, permitindo a queima de legendas dinâmicas, inserção de marca d'água (logo do canal), adição de identificador de usuário (@handle) e customização de faixas de abertura/rodapé. Os clipes são processados em paralelo para aproveitar múltiplos núcleos de CPU.

---

## Como funciona
1. **Análise de Dimensões:** Utiliza o `ffprobe` para extrair a largura e altura originais do vídeo fonte (`_obter_dimensoes_video`).
2. **Layouts Verticais (`_filtro_layout`):**
   - **`preenchido`:** Aplica zoom e corte central para preencher totalmente o canvas 1080x1920 sem bordas pretas.
   - **`blur`:** Mantém o vídeo original inteiro e centralizado, preenchendo o fundo com uma versão desfocada (`gblur`) do próprio vídeo. Calcula a posição exata de término do vídeo para alinhar corretamente elementos dinâmicos na base.
3. **Processamento de Elementos Visuais (`_cortar_um_clipe`):**
   - Sobrepõe a marca d'água (logo) configurada com transparência e margens definidas.
   - Desenha uma faixa colorida de abertura no rodapé (quando há gancho definido nas legendas) utilizando o comando `drawbox` do FFmpeg.
   - Gera e aplica legendas dinâmicas baseadas em arquivos `.ass` criados pelo módulo de transcrição.
4. **Execução Paralela (`cortar_video`):**
   - Utiliza um `ThreadPoolExecutor` para executar múltiplos processos do FFmpeg em paralelo (limitado por padrão ao número de núcleos da CPU ou até um teto de 4 processos).
   - Reordena cronologicamente os clipes gerados com base no tempo de início no vídeo original antes de retornar a lista final.

---

## Dependências
- **Bibliotecas Python nativas:** `os`, `subprocess`, `tempfile`, `concurrent.futures`.
- **Módulos internos:** 
  - `captions` (funções `gerar_ass_para_corte`, `escapar_caminho_ffmpeg`, constante `RODAPE_DURACAO`)
  - `utils` (função `slugificar`)
- **Ferramentas externas:** `ffmpeg` e `ffprobe` instalados e acessíveis no PATH do sistema operacional.

---

## Pontos de configuração (o que costuma mudar)
- **Marca d'água (`assets/logo.png` / `LARGURA_LOGO_PROPORCAO` / `MARGEM_LOGO` / `OPACIDADE_LOGO`):** Define o caminho padrão da imagem, o tamanho proporcional em relação à largura do vídeo final, espaçamento das bordas e nível de opacidade.
- **Handle da conta (`HANDLE_PADRAO`):** Define o identificador padrão exibido semi-transparentemente no canto inferior esquerdo dos clipes.
- **Faixa de rodapé (`ALTURA_FAIXA_RODAPE` / `COR_FAIXA_RODAPE`):** Controla a altura em pixels e a cor em formato hexadecimal do FFmpeg (ex: `"0xFF0000"`) utilizada para destacar o gancho do corte nos primeiros segundos.
- **Parâmetros de Codificação (`cortar_video`):** Ajustáveis na chamada da função principal, incluindo o preset de velocidade do codificador libx264 (`preset`), fator de qualidade (`crf`), pasta de saída e escolha entre os layouts `preenchido` ou `blur`.

---

## Histórico de mudanças

| Data | Autor | Hash do commit | Descrição da alteração |
| :--- | :--- | :--- | :--- |
| 29/09/2026 | Gustavo Rockembach | bf33694 | Descomentado as linhas de handle e rodape e alterada a cor da faixa do rodape |