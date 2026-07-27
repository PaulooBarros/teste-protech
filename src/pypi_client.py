import logging
from datetime import datetime
from typing import Dict, Optional

import requests

logger = logging.getLogger("dependency_report.pypi")

LICENSE_CLASSIFIER_PREFIX = "License :: "
MAX_LICENSE_LENGTH = 100

# Campos devolvidos por fetch_package_info. Nomeados em um só lugar para que
# o retorno de sucesso e o de falha não saiam de sincronia.
FIELDS = (
    "pypi_version",
    "description",
    "license",
    "last_release_date",
    "vulnerabilities",
)


def fetch_package_info(package_name: str) -> Dict[str, Optional[str]]:
    url = f"https://pypi.org/pypi/{package_name}/json"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        payload = response.json()

        info = payload.get("info", {})

        return {
            "pypi_version": info.get("version"),
            "description": info.get("summary"),
            "license": _extract_license(info),
            "last_release_date": _extract_last_release_date(payload.get("releases", {})),
            "vulnerabilities": _count_vulnerabilities(payload),
        }
    except requests.RequestException as exc:
        logger.error("Falha ao consultar PyPI para %s: %s", package_name, exc)
        return dict.fromkeys(FIELDS)


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
