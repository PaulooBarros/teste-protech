"""Ponto de entrada da aplicação de relatório de dependências."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Iterable
from pathlib import Path
from typing import TypeVar

from tqdm import tqdm

from src.logger import DEFAULT_LOG_FILE, configure_logger
from src.models import DependencyInfo
from src.parsers import parse_pyproject, parse_requirements
from src.pypi_client import PyPiClient
from src.report import build_report
from src.snyk_scraper import SnykScraper

# O parser é escolhido pela extensão, e não pelo nome exato do arquivo:
# nomes como `requirements-dev.txt` são comuns e devem funcionar.
T = TypeVar("T")

PARSERS_BY_SUFFIX = {
    ".txt": parse_requirements,
    ".toml": parse_pyproject,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gera relatório Excel de dependências Python com dados do PyPI e Snyk."
    )
    parser.add_argument("--input", required=True, help="Arquivo requirements.txt ou pyproject.toml")
    parser.add_argument("--output", required=True, help="Arquivo Excel de saída")
    parser.add_argument("--driver", help="Caminho opcional para o ChromeDriver")
    parser.add_argument(
        "--show-browser",
        action="store_true",
        help="Executa o navegador em modo visível, útil para depurar o scraping",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=DEFAULT_LOG_FILE,
        help=f"Arquivo de log da execução (padrão: {DEFAULT_LOG_FILE})",
    )
    parser.add_argument(
        "--no-log-file",
        action="store_true",
        help="Não grava log em arquivo, apenas no console",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Mostra também as mensagens de depuração no console",
    )
    return parser.parse_args()


def load_dependencies(source_path: Path, logger: logging.Logger) -> dict[str, str | None]:
    """Lê as dependências do arquivo de entrada."""
    if not source_path.exists():
        raise SystemExit(f"Arquivo de entrada não encontrado: {source_path}")

    parser = PARSERS_BY_SUFFIX.get(source_path.suffix.lower())
    if parser is None:
        suportados = ", ".join(PARSERS_BY_SUFFIX)
        raise SystemExit(
            f"Formato não suportado: {source_path.name}. Use um arquivo {suportados}."
        )

    dependencies = parser(source_path)
    logger.info("%d dependências encontradas em %s", len(dependencies), source_path)
    return dependencies


def collect_dependency(
    name: str,
    requested_version: str | None,
    pypi: PyPiClient,
    scraper: SnykScraper,
    logger: logging.Logger,
) -> DependencyInfo:
    """Consolida os dados do PyPI e do Snyk para uma dependência.

    Falhas são registradas e convertidas em uma linha com o campo `notas`
    preenchido, para que uma dependência problemática não derrube o relatório
    inteiro.
    """
    logger.info("Processando dependência: %s", name)
    try:
        package_info = pypi.fetch(name)
        snyk_data = scraper.fetch(name)
    except Exception as exc:
        logger.exception("Erro inesperado ao processar %s", name)
        return DependencyInfo(name=name, requested_version=requested_version, notes=str(exc))

    return DependencyInfo(
        name=name,
        requested_version=requested_version,
        pypi_version=package_info.get("pypi_version"),
        description=package_info.get("description"),
        license=package_info.get("license"),
        last_release_date=package_info.get("last_release_date"),
        snyk_score=snyk_data.score,
        vulnerabilities_total=snyk_data.vulnerabilities_total,
        vulnerabilities_latest=snyk_data.vulnerabilities_latest,
        vulnerabilities_pypi=package_info.get("vulnerabilities"),
    )


def _with_progress(items: Iterable[T], total: int) -> Iterable[T]:
    """Envolve a iteração em uma barra de progresso.

    Cada dependência exige uma consulta ao PyPI e outra ao portal, então uma
    lista grande leva minutos. A barra informa quanto falta e o tempo
    estimado, o que os registros de log sozinhos não dizem.

    `disable=None` desliga a barra automaticamente quando a saída não é um
    terminal — redirecionada para arquivo ou executada em integração
    contínua, ela só produziria caracteres de controle.
    """
    return tqdm(
        items,
        total=total,
        desc="Consultando dependências",
        unit="pacote",
        disable=None,
    )


def main() -> None:
    args = parse_args()
    logger = configure_logger(
        log_file=None if args.no_log_file else args.log_file,
        verbose=args.verbose,
    )

    dependencies = load_dependencies(Path(args.input), logger)

    collected: list[DependencyInfo] = []
    scraper = SnykScraper(
        driver_path=Path(args.driver) if args.driver else None,
        headless=not args.show_browser,
    )
    with PyPiClient() as pypi, scraper:
        for name, version in _with_progress(dependencies.items(), len(dependencies)):
            collected.append(collect_dependency(name, version, pypi, scraper, logger))

    destination = Path(args.output)
    build_report(collected, destination)
    logger.info("Relatório gerado em %s", destination)


if __name__ == "__main__":
    main()
