"""Modelos de dados da aplicação."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class DependencyInfo:
    """Dados consolidados de uma dependência.

    Só o nome é obrigatório: quando o PyPI ou o Snyk não respondem, a linha é
    gerada assim mesmo, com os campos que faltaram vazios e o motivo em
    `notes`. O modelo não conhece o formato da planilha — a disposição das
    colunas é responsabilidade de `src.report`.

    As três contagens de vulnerabilidade vêm de fontes distintas e são
    mantidas separadas de propósito: `vulnerabilities_total` e
    `vulnerabilities_latest` vêm do portal Snyk, enquanto
    `vulnerabilities_pypi` vem da base OSV, via API do PyPI. Elas podem
    divergir, e a divergência é informação — não erro a ser reconciliado.
    """

    name: str
    requested_version: str | None = None
    pypi_version: str | None = None
    description: str | None = None
    license: str | None = None
    last_release_date: datetime | None = None
    snyk_score: int | None = None
    vulnerabilities_total: int | None = None
    vulnerabilities_latest: int | None = None
    vulnerabilities_pypi: int | None = None
    notes: str | None = None
