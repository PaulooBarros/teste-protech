from dataclasses import dataclass
from datetime import datetime
from typing import Optional

# Datas são gravadas como texto: o Excel não aceita datetime com fuso horário,
# e o formato ISO curto continua ordenável alfabeticamente na planilha.
DATE_FORMAT = "%Y-%m-%d"


@dataclass
class DependencyInfo:
    name: str
    requested_version: Optional[str] = None
    pypi_version: Optional[str] = None
    description: Optional[str] = None
    license: Optional[str] = None
    last_release_date: Optional[datetime] = None
    snyk_score: Optional[float] = None
    vulnerabilities_total: Optional[int] = None
    vulnerabilities_latest: Optional[int] = None
    notes: Optional[str] = None

    def to_row(self) -> list:
        return [
            self.name,
            self.requested_version or "",
            self.pypi_version or "",
            self.description or "",
            self.license or "",
            self.last_release_date.strftime(DATE_FORMAT) if self.last_release_date else "",
            self.snyk_score if self.snyk_score is not None else "",
            self.vulnerabilities_total if self.vulnerabilities_total is not None else "",
            self.vulnerabilities_latest if self.vulnerabilities_latest is not None else "",
            self.notes or "",
        ]
