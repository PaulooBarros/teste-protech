# Dependências Python e Relatório de Segurança

[![CI](https://github.com/PaulooBarros/teste-protech/actions/workflows/ci.yml/badge.svg)](https://github.com/PaulooBarros/teste-protech/actions/workflows/ci.yml)

Este projeto lê dependências Python de `requirements.txt` ou `pyproject.toml`, coleta informações do PyPI e do portal Snyk usando Selenium, e gera uma planilha Excel com os resultados.

## Estrutura

- `src/main.py`: ponto de entrada e orquestração da coleta
- `src/parsers.py`: leitura de `requirements.txt` e `pyproject.toml`
- `src/pypi_client.py`: consulta a API pública do PyPI
- `src/snyk_scraper.py`: consulta o portal Snyk com Selenium
- `src/report.py`: gera o relatório em Excel
- `src/models.py`: modelos de dados
- `src/logger.py`: configuração de logs
- `tests/`: testes automatizados
- `examples/`: arquivo de entrada de exemplo e a planilha resultante

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

3. O mesmo vale para `pyproject.toml`:

```bash
python -m src.main --input pyproject.toml --output report.xlsx
```

> A aplicação é executada como módulo (`-m src.main`). Chamar
> `python src/main.py` falha com `ModuleNotFoundError`, porque nesse modo o
> Python coloca `src/` no `sys.path` em vez da raiz do projeto.

O parser é escolhido pela extensão do arquivo, então nomes como
`requirements-dev.txt` também funcionam.

### Analisando um projeto remoto

O enunciado pede para ler as dependências "de um projeto Python", sem
restringir onde o projeto está. O `--input` aceita também uma URL, o que
permite auditar um repositório sem cloná-lo:

```bash
python -m src.main \
  --input https://raw.githubusercontent.com/psf/requests/main/requirements-dev.txt \
  --output requests.xlsx
```

A extensão é lida do caminho da URL, ignorando a query string — portanto
`.../requirements.txt?raw=1` continua sendo tratado como `.txt`. Arquivos
acima de 5 MB são recusados.

## Exemplo

A pasta `examples/` traz arquivos de entrada nos dois formatos aceitos e a
planilha gerada, para consultar o resultado sem precisar executar a aplicação.

```bash
python -m src.main --input examples/requirements-exemplo.txt --output examples/report.xlsx
```

Os dois exemplos incluem de propósito o `pycrypto`, um pacote abandonado com
score 44, para demonstrar o destaque visual.

Para verificar o outro formato de entrada, o `examples/pyproject-exemplo.toml`
declara dependências tanto no padrão da PEP 621 quanto no do Poetry, e ambos
são lidos na mesma execução:

```bash
python -m src.main --input examples/pyproject-exemplo.toml --output pyproject-report.xlsx
```

### Opções

| Opção | Descrição |
|---|---|
| `--input` | Caminho do `requirements.txt` ou `pyproject.toml` (obrigatório) |
| `--output` | Caminho do arquivo `.xlsx` gerado (obrigatório) |
| `--driver` | Caminho para um ChromeDriver específico, se não quiser usar o automático |
| `--show-browser` | Abre o navegador em modo visível, útil para depurar o scraping |
| `--log-file` | Arquivo de log da execução (padrão: `logs/dependency_report.log`) |
| `--no-log-file` | Grava apenas no console, sem arquivo |
| `--verbose` | Mostra também as mensagens de depuração no console |

## Acompanhamento da execução

Cada dependência exige uma consulta ao PyPI e outra ao portal, então uma lista
grande leva minutos. Uma barra mostra o andamento e o tempo estimado:

```
Consultando dependências:  50%|█████     | 3/6 [00:08<00:08, 2.7s/pacote]
```

Ela se desliga sozinha quando a saída não é um terminal — redirecionada para
arquivo ou executada em integração contínua, só produziria caracteres de
controle. Nesses casos, o registro de log continua indicando o andamento.

## Logs

A execução é registrada em dois lugares, com finalidades diferentes:

| Destino | Nível | Para quê |
|---|---|---|
| Console | `INFO` em diante | acompanhar o andamento |
| `logs/dependency_report.log` | `DEBUG` em diante | diagnosticar depois que o problema aconteceu |

O arquivo guarda detalhes que só atrapalhariam no console — por exemplo,
cada linha do `requirements.txt` que foi ignorada e por quê. Use
`--verbose` para ver essas mensagens também na tela.

O arquivo rotaciona a cada 1 MB, mantendo os três anteriores, para que uma
execução sobre um projeto grande não cresça sem limite.

Não conseguir gravar o log não interrompe o relatório: um aviso vai para o
console e a execução segue.

## Dados coletados

Do portal Snyk, via Selenium: o *Package Health Score* (0 a 100) e duas
contagens de vulnerabilidades.

Da API pública do PyPI: última versão, descrição, licença, data da última
publicação e uma terceira contagem de vulnerabilidades, vinda da base OSV.

### Por que três colunas de vulnerabilidades

Os números medem coisas diferentes, e reduzi-los a um só esconderia
informação relevante para uma análise de segurança:

| Coluna | Fonte | O que mede |
|---|---|---|
| Vulnerabilidades (total) | Snyk | histórico completo do pacote |
| Vulnerabilidades (versão atual) | Snyk | quantas ainda afetam a última versão |
| Vulnerabilidades (PyPI/OSV) | PyPI | idem, segundo uma base independente |

As duas primeiras vêm da mesma fonte e se relacionam: o total é um
superconjunto. `6 total / 0 atual` indica um pacote com histórico mas bem
mantido, enquanto `4 total / 2 atual` é sinal de alerta.

A terceira vem de outra base de dados e serve para **cruzar as fontes**. Nos
seis pacotes de `examples/`, ela concorda com a coluna do Snyk em cinco. No
`pycrypto` elas divergem — o OSV conta 4 e o Snyk 2 —, porque as bases
avaliam de forma diferente quais faixas de versão são afetadas. Como não há
como afirmar qual está certa, a planilha mostra as duas em vez de escolher
uma e esconder a divergência.

Ela também funciona como rede de segurança: se o scraping do Snyk falhar, a
contagem do PyPI ainda aparece, porque vem da requisição que já era feita de
qualquer forma.

### Zero é diferente de vazio

Nas colunas de vulnerabilidade e de score, `0` e célula vazia não significam
a mesma coisa:

- **`0`** — a fonte respondeu e afirma que não há nenhuma
- **vazia** — não foi possível obter o dado

Um pacote não consultado nunca aparece como `0`, e nunca é destacado em
vermelho. Ausência de dado disfarçada de boa notícia seria o pior erro
possível em uma ferramenta de análise de segurança.

### Por que a busca do portal não é usada

O scraper acessa direto `https://security.snyk.io/package/pip/{nome}` em vez
de digitar no campo de busca. A busca é arriscada: pesquisar por `flask`
retorna `fflask` — um pacote malicioso que imita o nome — entre os primeiros
resultados. Uma lógica de "clicar no primeiro resultado" coletaria dados do
pacote errado sem nenhum aviso. Os nomes são normalizados conforme a PEP 503
antes de montar a URL.

## Testes

Instale as dependências de desenvolvimento e execute a suíte:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
```

> Use `python -m pytest` em vez de `pytest`: o diretório de scripts do Python
> nem sempre está no `PATH`, e essa forma funciona em qualquer instalação.

Comandos úteis durante o desenvolvimento:

```bash
python -m pytest -v                        # lista cada teste pelo nome
python -m pytest tests/test_parsers.py -v   # só um arquivo
python -m pytest -k "destaque" -v           # só os testes do destaque visual
```

### Relatório em HTML

Para visualizar o resultado em uma página, em vez da saída do terminal:

```bash
python -m pytest --html=testes.html --self-contained-html
```

Abra o `testes.html` gerado no navegador. O `--self-contained-html` embute o
CSS no próprio arquivo, o que permite compartilhá-lo isoladamente.

Os testes cobrem a leitura de dependências, o tratamento das respostas do
PyPI e a geração da planilha — inclusive os limites do destaque visual
(scores 64, 65 e ausente). Não há testes de navegador: o scraping depende do
HTML de um site externo, que muda sem aviso, então essa parte é validada
manualmente.

## Qualidade de código

O projeto usa o [Ruff](https://docs.astral.sh/ruff/) como linter e formatador:

```bash
python -m ruff check .        # verifica
python -m ruff check . --fix  # corrige o que é seguro corrigir
python -m ruff format .       # formata
```

As regras ficam declaradas em `ruff.toml`, em vez de depender do conjunto
padrão da ferramenta — esse padrão muda entre versões, e isso faria a
integração contínua passar hoje e falhar amanhã sem que nada no código
mudasse.

## Integração contínua

O `.github/workflows/ci.yml` executa o linter e a suíte de testes a cada
push, nas versões 3.11, 3.12 e 3.13 do Python. A 3.11 é o mínimo suportado
por causa do `tomllib`; as demais confirmam que nada quebra nas seguintes.

O CI não precisa de Chrome, porque a suíte não abre navegador — roda em
segundos.

## Observações

- A planilha destaca em vermelho as linhas com `Score < 65`. A segunda aba,
  "Legenda", descreve cada coluna e o critério do destaque.
- Falhas em uma dependência não interrompem a execução: o erro é registrado no
  log, a coluna "Notas" é preenchida e o processamento segue para a próxima.
- Se um pacote não existir no Snyk, a linha é gerada com o score e as duas
  colunas do portal vazios — os dados do PyPI, inclusive a contagem OSV,
  continuam preenchidos.
- Os dados do portal mudam com o tempo. Duas planilhas geradas em dias
  diferentes podem divergir: o `django`, por exemplo, passou de 158 para 161
  vulnerabilidades no intervalo de algumas horas.
