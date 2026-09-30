# Propósito
O script `scripts/atualizar_docs.py` tem como propósito automatizar a criação e a atualização de arquivos de documentação em Markdown para os módulos escritos em Python de um repositório. Ele roda tipicamente integrado a um fluxo de CI/CD (como o GitHub Actions) a cada push, utilizando a inteligência artificial do Google Gemini para analisar os códigos modificados e gerar documentações precisas e atualizadas.

# Como funciona
O script executa o seguinte fluxo de execução:
1. **Verificação de ambiente**: Valida a presença da chave de API do Gemini (`GEMINI_API_KEY`) nas variáveis de ambiente.
2. **Identificação do commit base**: Através da função `obter_commit_base()`, o script determina o ponto de partida ideal para a comparação do Git. Ele prioriza a variável `BEFORE_SHA` (fornecida pelo GitHub Actions para abranger todo o lote de commits de um push), recorre ao `HEAD~1` como primeiro fallback, e utiliza o hash de árvore vazia (`ARVORE_VAZIA`) como segundo fallback caso seja o primeiro commit do repositório.
3. **Mapeamento de alterações**: Lista todos os arquivos `.py` modificados entre o commit base e o `HEAD`, aplicando filtros opcionais baseados em pastas monitoradas.
4. **Coleta de diffs e códigos**: Para cada arquivo alterado, extrai o diff correspondente utilizando o Git e lê o conteúdo atualizado do código-fonte. Também verifica se já existe uma documentação prévia associada na pasta de destino.
5. **Geração via IA**: Monta um prompt contextualizado contendo o diff, o código atual e a documentação anterior (se houver), enviando-o para o modelo Gemini (`gemini-3.5-flash-lite`).
6. **Persistência**: Salva ou atualiza o resultado gerado em formato Markdown dentro da pasta de documentação configurada (`docs/`).

# Dependências
As dependências necessárias para a execução do script são:
- Python 3.x
- Bibliotecas padrão do Python: `os`, `subprocess`, `sys`, `pathlib`
- Biblioteca de IA do Google: `google-genai`
- Ferramenta de controle de versão: `git` (disponível no PATH do sistema)
- Variáveis de ambiente obrigatórias: `GEMINI_API_KEY`

# Pontos de configuração (o que costuma mudar)
- `MODELO`: Define qual versão do modelo da API do Gemini será utilizada (atualmente configurado como `"gemini-3.5-flash-lite"`).
- `PASTA_DOCS`: O diretório onde os arquivos de documentação em Markdown são salvos (padrão: `Path("docs")`).
- `PASTAS_MONITORADAS`: Lista opcional para restringir a variação de arquivos a caminhos específicos do repositório (ex: `["youtube-clipper-completo"]`).
- Variáveis de ambiente no CI/CD: Como `BEFORE_SHA`, injetada pelo ambiente de integração contínua.

# Histórico de mudanças

| Data | Autor | Descrição da Mudança |
| :--- | :--- | :--- |
| 2024-03-30 | Sistema / IA | Criação inicial da documentação e introdução da lógica robusta de identificação de commit base (`obter_commit_base`). |