# Dependências Python e Relatório de Segurança

Este projeto lê dependências Python de `requirements.txt` ou `pyproject.toml`, coleta informações do PyPI e do portal Snyk usando Selenium, e gera uma planilha Excel com os resultados.

## Estrutura

- `src/main.py`: ponto de entrada e orquestração da coleta
- `src/parsers.py`: leitura de `requirements.txt` e `pyproject.toml`
- `src/pypi_client.py`: consulta a API pública do PyPI
- `src/snyk_scraper.py`: consulta o portal Snyk com Selenium
- `src/report.py`: gera o relatório em Excel
- `src/models.py`: modelos de dados
- `src/logger.py`: configuração de logs

## Pré-requisitos

- Python 3.11+ (o parser de TOML usa o `tomllib` da biblioteca padrão)
- Google Chrome instalado

Não é preciso baixar o ChromeDriver manualmente: o Selenium Manager, embutido
desde a versão 4.6, resolve o driver compatível automaticamente.

## Como executar

1. Instale as dependências:

```bash
python -m pip install -r requirements.txt
```

2. Execute a aplicação a partir da raiz do projeto:

```bash
python -m src.main --input requirements.txt --output report.xlsx
```

3. Para `pyproject.toml`:

```bash
python -m src.main --input pyproject.toml --output report.xlsx
```

> A aplicação é executada como módulo (`-m src.main`). Chamar
> `python src/main.py` falha com `ModuleNotFoundError`, porque nesse modo o
> Python coloca `src/` no `sys.path` em vez da raiz do projeto.

### Opções

| Opção | Descrição |
|---|---|
| `--input` | Caminho do `requirements.txt` ou `pyproject.toml` (obrigatório) |
| `--output` | Caminho do arquivo `.xlsx` gerado (obrigatório) |
| `--driver` | Caminho para um ChromeDriver específico, se não quiser usar o automático |
| `--show-browser` | Abre o navegador em modo visível, útil para depurar o scraping |

## Dados coletados

Da API pública do PyPI: última versão, descrição, licença e data da última
publicação.

Do portal Snyk, via Selenium: o *Package Health Score* (0 a 100) e a contagem
de vulnerabilidades.

### Por que duas colunas de vulnerabilidades

O Snyk expõe dois números diferentes, e ambos vão para a planilha:

- **Vulnerabilidades (total)** — histórico completo do pacote
- **Vulnerabilidades (versão atual)** — quantas ainda afetam a última versão

O total é um superconjunto, não um período separado. `6 total / 0 atual`
indica um pacote com histórico mas bem mantido, enquanto `4 total / 2 atual`
é sinal de alerta. Mostrar apenas um dos dois esconderia informação relevante
para a análise.

### Por que a busca do portal não é usada

O scraper acessa direto `https://security.snyk.io/package/pip/{nome}` em vez
de digitar no campo de busca. A busca é arriscada: pesquisar por `flask`
retorna `fflask` — um pacote malicioso que imita o nome — entre os primeiros
resultados. Uma lógica de "clicar no primeiro resultado" coletaria dados do
pacote errado sem nenhum aviso. Os nomes são normalizados conforme a PEP 503
antes de montar a URL.

## Observações

- A planilha destaca em vermelho as linhas com `Score < 65`.
- Falhas em uma dependência não interrompem a execução: o erro é registrado no
  log, a coluna "Notas" é preenchida e o processamento segue para a próxima.
- Se um pacote não existir no Snyk, a linha é gerada com os campos de score e
  vulnerabilidades vazios.
