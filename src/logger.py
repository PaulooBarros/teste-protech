"""Configuração de logs da aplicação."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from tqdm import tqdm

LOGGER_NAME = "dependency_report"
DEFAULT_LOG_FILE = Path("logs") / "dependency_report.log"

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Um arquivo por vez, até 1 MB, guardando três anteriores. Sem rotação, uma
# execução sobre um projeto grande cresceria sem limite.
MAX_BYTES = 1_000_000
BACKUP_COUNT = 3


class TqdmLoggingHandler(logging.StreamHandler):
    """Saída de console que convive com a barra de progresso.

    Um `StreamHandler` comum escreve direto no terminal e embaralha a linha
    da barra. O `tqdm.write` apaga a barra, imprime a mensagem e redesenha
    logo abaixo. Sem barra ativa, comporta-se como um handler normal.
    """

    def emit(self, record: logging.LogRecord) -> None:
        try:
            tqdm.write(self.format(record), file=self.stream)
            self.flush()
        except RecursionError:  # tratada à parte, como faz a própria stdlib
            raise
        except Exception:  # noqa: BLE001 - registrar log não pode derrubar a aplicação
            # Mesmo tratamento do `StreamHandler` da biblioteca padrão:
            # `handleError` encaminha o problema sem propagar a exceção.
            self.handleError(record)


def configure_logger(
    log_file: Path | None = DEFAULT_LOG_FILE,
    verbose: bool = False,
) -> logging.Logger:
    """Prepara o log da aplicação.

    O console mostra o andamento (`INFO` em diante), enquanto o arquivo
    guarda tudo, inclusive `DEBUG`. A separação existe porque os dois têm
    finalidades diferentes: acompanhar a execução e diagnosticar um problema
    depois que ele aconteceu.

    Passar `log_file=None` desliga a gravação em arquivo.
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG)

    # Limpar permite reconfigurar sem acumular saídas duplicadas.
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    console = TqdmLoggingHandler()
    console.setLevel(logging.DEBUG if verbose else logging.INFO)
    console.setFormatter(formatter)
    logger.addHandler(console)

    if log_file is not None:
        file_handler = _build_file_handler(log_file, formatter, logger)
        if file_handler is not None:
            logger.addHandler(file_handler)

    return logger


def _build_file_handler(
    log_file: Path,
    formatter: logging.Formatter,
    logger: logging.Logger,
) -> RotatingFileHandler | None:
    """Cria o arquivo de log, ou devolve `None` se não for possível.

    Não conseguir gravar o log não é motivo para abortar o relatório: o aviso
    vai para o console e a execução segue.
    """
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            log_file,
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            # Explícito porque no Windows o padrão é a codificação do sistema,
            # que corromperia os acentos das mensagens.
            encoding="utf-8",
        )
    except OSError as exc:
        logger.warning("Não foi possível gravar o log em %s: %s", log_file, exc)
        return None

    handler.setLevel(logging.DEBUG)
    handler.setFormatter(formatter)
    return handler
