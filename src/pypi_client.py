"""Consulta à API pública do PyPI."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

import requests
from requests.adapters import HTTPAdapter, Retry

logger = logging.getLogger("dependency_report.pypi")

BASE_URL = "https://pypi.org/pypi/{package}/json"

LICENSE_CLASSIFIER_PREFIX = "License :: "
MAX_LICENSE_LENGTH = 100

# Campos devolvidos por fetch(). Nomeados em um só lugar para que o retorno
# de sucesso e o de falha não saiam de sincronia.
FIELDS = (
    "pypi_version",
    "description",
    "license",
    "last_release_date",
    "vulnerabilities",
)

# Situações temporárias que justificam nova tentativa. O 404 fica de fora de
# propósito: pacote inexistente não passa a existir por insistência.
RETRIABLE_STATUS = (429, 500, 502, 503, 504)


class PyPiClient:
    """Cliente da API pública do PyPI.

    Mantém uma `Session` para reaproveitar a conexão entre as consultas, em
    vez de abrir uma nova a cada dependência, e repete automaticamente as
    falhas temporárias com espera progressiva.

    Use como gerenciador de contexto para garantir o fechamento da conexão::

        with PyPiClient() as client:
            dados = client.fetch("flask")
    """

    def __init__(
        self,
        session: Optional[requests.Session] = None,
        timeout: int = 10,
        attempts: int = 3,
        backoff: float = 0.5,
    ) -> None:
        self._timeout = timeout
        self._session = session or self._build_session(attempts, backoff)

    @staticmethod
    def _build_session(attempts: int, backoff: float) -> requests.Session:
        retry = Retry(
            total=attempts - 1,
            backoff_factor=backoff,
            status_forcelist=RETRIABLE_STATUS,
            allowed_methods=frozenset({"GET"}),
        )
        session = requests.Session()
        session.mount("https://", HTTPAdapter(max_retries=retry))
        return session

    def __enter__(self) -> "PyPiClient":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        self.close()
        return False

    def close(self) -> None:
        self._session.close()

    def fetch(self, package_name: str) -> Dict[str, Any]:
        """Retorna os dados públicos de um pacote.

        Falhas de rede não interrompem o relatório: viram campos vazios, com
        o motivo registrado no log.
        """
        try:
            response = self._session.get(
                BASE_URL.format(package=package_name), timeout=self._timeout
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            logger.error("Falha ao consultar PyPI para %s: %s", package_name, exc)
            return dict.fromkeys(FIELDS)

        info = payload.get("info", {})
        return {
            "pypi_version": info.get("version"),
            "description": info.get("summary"),
            "license": _extract_license(info),
            "last_release_date": _extract_last_release_date(payload.get("releases", {})),
            "vulnerabilities": _count_vulnerabilities(payload),
        }


def _count_vulnerabilities(payload: Dict) -> Optional[int]:
    """Conta as vulnerabilidades que o PyPI reporta para a versão mais recente.

    A origem é a base OSV, independente do Snyk, o que permite cruzar as duas
    fontes. O número não substitui o do portal: cobre apenas a versão atual,
    sem o histórico do pacote.
    """
    vulnerabilities = payload.get("vulnerabilities")
    return len(vulnerabilities) if isinstance(vulnerabilities, list) else None


def _extract_license(info: Dict) -> Optional[str]:
    """Descobre a licença testando as fontes na ordem de confiabilidade.

    O campo `license` está obsoleto: pacotes modernos usam `license_expression`
    (PEP 639) e os mais antigos só declaram a licença nos classificadores.
    Alguns projetos ainda despejam o texto integral da licença em `license`,
    por isso valores longos demais são descartados.
    """
    expression = info.get("license_expression")
    if expression:
        return expression

    legacy = (info.get("license") or "").strip()
    if legacy and len(legacy) <= MAX_LICENSE_LENGTH:
        return legacy

    for classifier in info.get("classifiers") or []:
        if classifier.startswith(LICENSE_CLASSIFIER_PREFIX):
            return classifier.rsplit(" :: ", 1)[-1]

    return None


def _extract_last_release_date(releases: Dict[str, list]) -> Optional[datetime]:
    last_date = None
    for release_files in releases.values():
        for release in release_files:
            upload_time = release.get("upload_time_iso_8601") or release.get("upload_time")
            if not upload_time:
                continue
            try:
                parsed = datetime.fromisoformat(upload_time.replace("Z", "+00:00"))
            except ValueError:
                continue
            if last_date is None or parsed > last_date:
                last_date = parsed
    return last_date
