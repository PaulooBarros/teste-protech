"""Modelos de dados da aplicação."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class DependencyInfo:
    """Dados consolidados de uma dependência.

    Só o nome é obrigatório: quando o PyPI ou o Snyk não respondem, a linha é
    gerada assim mesmo, com os campos que faltaram vazios e o motivo em
    `notes`. O modelo não conhece o formato da planilha — a disposição das
    colunas é responsabilidade de `src.report`.
    """

    name: str
    requested_version: Optional[str] = None
    pypi_version: Optional[str] = None
    description: Optional[str] = None
    license: Optional[str] = None
    last_release_date: Optional[datetime] = None
    snyk_score: Optional[int] = None
    vulnerabilities_total: Optional[int] = None
    vulnerabilities_latest: Optional[int] = None
    notes: Optional[str] = None
