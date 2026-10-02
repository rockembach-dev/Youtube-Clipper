# Documentação do Módulo: `youtube-clipper-completo/main.py`

## Propósito
Este módulo atua como o ponto de entrada principal (orquestrador) do pipeline automatizado de geração de cortes virais a partir de vídeos do YouTube. Sua função é coordenar a execução sequencial de todas as etapas do processo: download do vídeo, transcrição por IA, análise estratégica de conteúdo para identificação de trechos relevantes, recorte e pós-processamento dos clipes, e geração de relatórios em formato JSON.

---

## Como funciona
O script opera via linha de comando (`argparse`), aceitando uma URL do YouTube e diversos parâmetros opcionais para customizar o comportamento do pipeline. O fluxo de execução segue as seguintes etapas:

1. **Análise de Argumentos:** Processa as opções de entrada fornecidas pelo usuário (como modelo Whisper, quantidade de cortes, modo rápido, formato horizontal/vertical, layout, legendas, entre outros).
2. **Download:** Utiliza o módulo `downloader` para baixar o vídeo do YouTube e obter seu título.
3. **Organização de Diretórios:** Cria uma subpasta dedicada dentro do diretório `clipes/` baseada no título sanitizado do vídeo (via `slugificar`).
4. **Transcrição:** Aciona o módulo `transcriber` para gerar os segmentos de texto e o mapeamento de palavras do vídeo, salvando o resultado bruto em um arquivo `transcricao.txt`.
5. **Análise de Conteúdo:** Executa a estratégia de seleção de cortes escolhida pelo usuário (análise local gratuita baseada em heurísticas ou via API do Claude).
6. **Recorte e Edição:** Envia os trechos identificados para o módulo `cutter`, que realiza a edição, redimensionamento (vertical/horizontal), aplicação de legendas dinâmicas, marcas d'água e handles conforme os parâmetros.
7. **Relatório Final:** Compila as informações dos clipes gerados e suas respectivas legendas sugeridas em um arquivo estruturado `relatorio_cortes.json`.

---

## Dependências
O módulo depende de bibliotecas nativas do Python e de módulos internos do projeto:

* **Módulos nativos:** `argparse`, `json`, `os`
* **Módulos internos:**
  * `downloader` (função `baixar_video`)
  * `transcriber` (funções `transcrever`, `formatar_transcricao_para_analise`)
  * `analyzer_free` (função `analisar_transcricao_local`)
  * `analyzer` (função opcional `analisar_transcricao` via API)
  * `cutter` (função `cortar_video`)
  * `postagem` (função `gerar_legenda_post`)
  * `utils` (função `slugificar`)

---

## Pontos de configuração (o que costuma mudar)
Os parâmetros ajustáveis são passados principalmente via argumentos de linha de comando (`argparse`), permitindo modificar o comportamento do pipeline sem alterar o código:

* **`--modelo-whisper`**: Define o modelo de transcrição (padrão: `small`). Pode ser alterado para `base`, `medium`, `large`, etc.
* **`--qtd-cortes`**: Número alvo de clipes a serem gerados (padrão: `12`).
* **`--horizontal`**: Flag para desativar a conversão automática para o formato vertical (9:16).
* **`--analise`**: Escolhe o motor de análise de texto entre `local` (gratuito) e `api` (Claude, requer chave de API).
* **`--layout`**: Define o estilo de preenchimento do vídeo vertical (`preenchido` ou `blur`).
* **`--sem-legenda`**: Desativa a queima de legendas dinâmicas nos clipes gerados.
* **`--paralelo`**: Controla a quantidade de clipes processados simultaneamente.
* **`--rapido`**: Ativa o modo de alta velocidade (força o modelo Whisper `base` e preset de corte `ultrafast`).
* **`--sem-marca-dagua` / `--sem-handle`**: Controlam a exibição de elementos visuais de identificação nos clipes.

---

## Histórico de mudanças

| Data | Hash do commit | Autor | Descrição da alteração |
| :--- | :--- | :--- | :--- |
| 02/10/2026 | d430e59 | Gustavo Rockembach | Retorno à versão anterior, removendo o import de `datetime`, o banner customizado de teste, a geração do campo `data_geracao` no relatório JSON e a criação do arquivo bônus `resumo_rapido.md`. |