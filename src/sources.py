"""Leitura do arquivo de dependências, local ou remoto.

O enunciado pede para ler as dependências "de um projeto Python", sem
restringir onde o projeto está. Este módulo resolve as duas origens possíveis
e entrega o conteúdo já em texto, deixando a interpretação para `parsers`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests

logger = logging.getLogger("dependency_report.sources")

URL_SCHEMES = ("http", "https")
DEFAULT_TIMEOUT = 15

# Um requirements.txt costuma ter alguns milhares de bytes. O limite evita
# que um endereço apontando para um arquivo enorme trave a aplicação.
MAX_SIZE_BYTES = 5 * 1024 * 1024


class SourceError(Exception):
    """Falha ao obter o arquivo de dependências."""


@dataclass(frozen=True)
class Source:
    """Conteúdo do arquivo de dependências e como interpretá-lo."""

    text: str
    suffix: str
    origin: str


def is_url(location: str | Path) -> bool:
    return urlparse(str(location)).scheme in URL_SCHEMES


def read_source(location: str | Path, timeout: int = DEFAULT_TIMEOUT) -> Source:
    """Devolve o conteúdo do arquivo, venha ele do disco ou de uma URL."""
    location = str(location)
    if is_url(location):
        return _read_from_url(location, timeout)
    return _read_from_disk(location)


def _read_from_disk(location: str) -> Source:
    path = Path(location)
    if not path.exists():
        raise SourceError(f"Arquivo de entrada não encontrado: {path}")

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SourceError(f"Não foi possível ler {path}: {exc}") from exc

    return Source(text=text, suffix=path.suffix.lower(), origin=str(path))


def _read_from_url(url: str, timeout: int) -> Source:
    logger.info("Baixando o arquivo de dependências de %s", url)
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise SourceError(f"Não foi possível baixar {url}: {exc}") from exc

    if len(response.content) > MAX_SIZE_BYTES:
        raise SourceError(
            f"O arquivo em {url} tem {len(response.content)} bytes, "
            f"acima do limite de {MAX_SIZE_BYTES}."
        )

    return Source(text=response.text, suffix=_suffix_from_url(url), origin=url)


def _suffix_from_url(url: str) -> str:
    """Extrai a extensão do caminho da URL, ignorando a query string.

    `.../requirements.txt?raw=1` deve ser tratado como `.txt`.
    """
    return Path(urlparse(url).path).suffix.lower()
