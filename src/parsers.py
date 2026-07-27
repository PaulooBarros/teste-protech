"""Leitura de dependências a partir de requirements.txt e pyproject.toml."""

from __future__ import annotations

import logging
import re
import tomllib
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("dependency_report.parsers")

# O especificador é preservado como foi declarado (">=3.0", "==2.31.0") em vez
# de reduzido ao número: é mais fiel ao que o projeto realmente pede.
REQUIREMENT_PATTERN = re.compile(
    r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)"  # nome do pacote
    r"(?:\[[^\]]*\])?"  # extras, irrelevantes para a consulta
    r"\s*(?P<version>[<>=!~].*)?$"  # especificador de versão
)

WHITESPACE_PATTERN = re.compile(r"\s+")


def parse_requirements(path: Path) -> Dict[str, Optional[str]]:
    """Lê as dependências declaradas em um `requirements.txt`."""
    dependencies: Dict[str, Optional[str]] = {}

    with path.open("r", encoding="utf-8") as handler:
        for line_number, line in enumerate(handler, start=1):
            requirement = _strip_annotations(line)
            if not requirement:
                continue

            parsed = _parse_requirement(requirement)
            if parsed is None:
                # Linhas de opção (-r, -e, --index-url) e hashes caem aqui.
                logger.debug("Linha %d ignorada em %s: %r", line_number, path.name, requirement)
                continue

            name, version = parsed
            dependencies[name] = version

    return dependencies


def parse_pyproject(path: Path) -> Dict[str, Optional[str]]:
    """Lê as dependências de um `pyproject.toml`.

    Cobre tanto o formato padrão (PEP 621, em `[project]`) quanto o do Poetry
    (em `[tool.poetry]`), já que ambos são comuns em projetos Python.
    """
    with path.open("rb") as handler:
        content = tomllib.load(handler)

    dependencies: Dict[str, Optional[str]] = {}
    dependencies.update(_extract_dependencies(content.get("project", {}).get("dependencies")))

    poetry = content.get("tool", {}).get("poetry", {})
    dependencies.update(_extract_dependencies(poetry.get("dependencies")))

    return dependencies


def _strip_annotations(line: str) -> str:
    """Remove comentários e marcadores de ambiente de uma linha."""
    without_comment = line.split("#", 1)[0]
    without_marker = without_comment.split(";", 1)[0]
    return without_marker.strip()


def _parse_requirement(requirement: str) -> Optional[tuple[str, Optional[str]]]:
    """Separa nome e especificador de versão, ou `None` se não for um requisito."""
    match = REQUIREMENT_PATTERN.match(requirement)
    if match is None:
        return None

    version = match.group("version")
    # Espaços são irrelevantes em um especificador PEP 508: ">= 4.17" e
    # ">=4.17" são equivalentes, então a planilha mostra sempre a forma curta.
    return match.group("name"), WHITESPACE_PATTERN.sub("", version) if version else None


def _extract_dependencies(raw_dependencies: Any) -> Dict[str, Optional[str]]:
    """Normaliza os dois formatos de declaração usados em `pyproject.toml`.

    O PEP 621 usa uma lista de strings (`["flask>=3.0"]`), enquanto o Poetry
    usa uma tabela (`flask = "^3.0"`), na qual o valor pode ser uma string ou
    uma tabela com a chave `version`.
    """
    if isinstance(raw_dependencies, dict):
        return _extract_from_table(raw_dependencies)
    if isinstance(raw_dependencies, list):
        return _extract_from_list(raw_dependencies)
    return {}


def _extract_from_table(raw_dependencies: Dict[str, Any]) -> Dict[str, Optional[str]]:
    dependencies: Dict[str, Optional[str]] = {}

    for name, metadata in raw_dependencies.items():
        # O Poetry declara a versão do interpretador junto das dependências.
        if name.lower() == "python":
            continue

        if isinstance(metadata, str):
            dependencies[name] = metadata
        elif isinstance(metadata, dict):
            dependencies[name] = metadata.get("version")
        else:
            dependencies[name] = None

    return dependencies


def _extract_from_list(raw_dependencies: list) -> Dict[str, Optional[str]]:
    dependencies: Dict[str, Optional[str]] = {}

    for entry in raw_dependencies:
        if not isinstance(entry, str):
            continue

        requirement = _strip_annotations(entry)
        parsed = _parse_requirement(requirement) if requirement else None
        if parsed is None:
            logger.debug("Dependência ignorada em pyproject.toml: %r", entry)
            continue

        name, version = parsed
        dependencies[name] = version

    return dependencies
