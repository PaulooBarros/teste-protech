"""Ponto de entrada da aplicação de relatório de dependências."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Dict, List, Optional

from src.logger import configure_logger
from src.models import DependencyInfo
from src.parsers import parse_pyproject, parse_requirements
from src.pypi_client import fetch_package_info
from src.report import build_report
from src.snyk_scraper import SnykScraper

PARSERS_BY_FILENAME = {
    "requirements.txt": parse_requirements,
    "pyproject.toml": parse_pyproject,
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
    return parser.parse_args()


def load_dependencies(source_path: Path, logger: logging.Logger) -> Dict[str, Optional[str]]:
    """Lê as dependências do arquivo de entrada."""
    if not source_path.exists():
        raise SystemExit(f"Arquivo de entrada não encontrado: {source_path}")

    parser = PARSERS_BY_FILENAME.get(source_path.name)
    if parser is None:
        suportados = ", ".join(PARSERS_BY_FILENAME)
        raise SystemExit(f"Arquivo de entrada inválido: {source_path}. Use um de: {suportados}")

    dependencies = parser(source_path)
    logger.info("%d dependências encontradas em %s", len(dependencies), source_path)
    return dependencies


def collect_dependency(
    name: str,
    requested_version: Optional[str],
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
        package_info = fetch_package_info(name)
        snyk_data = scraper.fetch(name)
    except Exception as exc:  # noqa: BLE001 - nenhuma dependência pode abortar o relatório
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
    )


def main() -> None:
    logger = configure_logger()
    args = parse_args()

    dependencies = load_dependencies(Path(args.input), logger)

    collected: List[DependencyInfo] = []
    with SnykScraper(
        driver_path=Path(args.driver) if args.driver else None,
        headless=not args.show_browser,
    ) as scraper:
        for name, version in dependencies.items():
            collected.append(collect_dependency(name, version, scraper, logger))

    destination = Path(args.output)
    build_report(collected, destination)
    logger.info("Relatório gerado em %s", destination)


if __name__ == "__main__":
    main()
