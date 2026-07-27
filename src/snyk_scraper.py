"""Coleta de dados de pacotes Python no portal Snyk usando Selenium."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from selenium import webdriver
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    NoSuchElementException,
    WebDriverException,
    TimeoutException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

logger = logging.getLogger("dependency_report.snyk")

PACKAGE_URL = "https://security.snyk.io/package/pip/{package}"

SCORE_SELECTOR = ".health-score .score-number"
VULNERABILITY_TABLE_SELECTOR = "table[data-snyk-test='PackageVulnerabilitiesTable: table']"
VULNERABILITY_ROW_SELECTOR = f"{VULNERABILITY_TABLE_SELECTOR} a[data-snyk-test='vuln table title']"
EMPTY_STATE_SELECTOR = ".empty-state__description"
FILTER_CHECKBOX_SELECTOR = ".toggle__field"

SCORE_PATTERN = re.compile(r"(\d+)\s*/\s*100")
TOTAL_VULNERABILITIES_PATTERN = re.compile(r"(\d+)\s+total\s+vulnerabilit", re.IGNORECASE)
NAME_SEPARATORS_PATTERN = re.compile(r"[-_.]+")


@dataclass
class SnykPackageData:
    """Dados coletados do portal Snyk para um pacote.

    Todos os campos são opcionais: quando o pacote não é encontrado ou a
    página muda de estrutura, o relatório é gerado com os campos vazios em
    vez de interromper a execução.
    """

    score: Optional[int] = None
    vulnerabilities_total: Optional[int] = None
    vulnerabilities_latest: Optional[int] = None


class SnykScraper:
    """Extrai informações de pacotes do portal Snyk.

    O navegador é reaproveitado entre consultas: abrir uma instância do Chrome
    por dependência tornaria a execução inviável em projetos com muitas
    dependências. Use como gerenciador de contexto para garantir que o
    navegador seja encerrado mesmo em caso de erro::

        with SnykScraper() as scraper:
            dados = scraper.fetch("flask")
    """

    def __init__(
        self,
        driver_path: Optional[Path] = None,
        timeout: int = 15,
        filter_timeout: int = 5,
        headless: bool = True,
    ) -> None:
        self._driver_path = driver_path
        self._timeout = timeout
        self._filter_timeout = filter_timeout
        self._headless = headless
        self._driver: Optional[webdriver.Chrome] = None

    def __enter__(self) -> "SnykScraper":
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        self.stop()
        return False

    def start(self) -> None:
        """Abre o navegador, caso ainda não esteja aberto."""
        if self._driver is not None:
            return

        options = Options()
        if self._headless:
            options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        # Sem driver_path explícito o Selenium Manager (embutido desde a
        # versão 4.6) baixa e configura o driver compatível automaticamente.
        service = ChromeService(str(self._driver_path)) if self._driver_path else None
        self._driver = webdriver.Chrome(service=service, options=options)

    def stop(self) -> None:
        """Encerra o navegador."""
        if self._driver is None:
            return
        try:
            self._driver.quit()
        except WebDriverException as exc:
            logger.warning("Falha ao encerrar o navegador: %s", exc)
        finally:
            self._driver = None

    def fetch(self, package_name: str) -> SnykPackageData:
        """Retorna score e contagens de vulnerabilidades de um pacote."""
        if self._driver is None:
            raise RuntimeError("O navegador não foi iniciado. Use start() ou o bloco with.")

        url = PACKAGE_URL.format(package=self._normalize_name(package_name))
        try:
            self._driver.get(url)
            self._wait_for_package_page()
        except TimeoutException:
            logger.warning("Pacote não encontrado no Snyk ou página demorou demais: %s", package_name)
            return SnykPackageData()
        except WebDriverException as exc:
            logger.error("Falha ao acessar o Snyk para %s: %s", package_name, exc)
            return SnykPackageData()

        latest, total = self._read_vulnerability_counts(package_name)
        return SnykPackageData(
            score=self._read_score(),
            vulnerabilities_total=total,
            vulnerabilities_latest=latest,
        )

    @staticmethod
    def _normalize_name(package_name: str) -> str:
        """Normaliza o nome conforme a PEP 503.

        O PyPI trata ``Flask``, ``flask`` e ``FLASK`` como o mesmo pacote, e
        runs de ``-``, ``_`` e ``.`` como um único ``-``.
        """
        return NAME_SEPARATORS_PATTERN.sub("-", package_name).lower()

    def _wait_for_package_page(self) -> None:
        WebDriverWait(self._driver, self._timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, SCORE_SELECTOR))
        )

    def _read_score(self) -> Optional[int]:
        """Lê o Package Health Score, exibido no formato ``90/100``."""
        try:
            raw_score = self._driver.find_element(By.CSS_SELECTOR, SCORE_SELECTOR).text
        except NoSuchElementException:
            logger.warning("Score não encontrado na página do pacote.")
            return None

        match = SCORE_PATTERN.search(raw_score)
        if match is None:
            logger.warning("Formato inesperado de score: %r", raw_score)
            return None
        return int(match.group(1))

    def _read_vulnerability_counts(self, package_name: str) -> tuple[Optional[int], Optional[int]]:
        """Retorna (vulnerabilidades na versão atual, total do pacote).

        A tabela do portal vem filtrada por padrão pelo controle "Show only
        direct vulnerabilities in latest version". Contamos as linhas nesse
        estado e depois desligamos o filtro para obter o total.
        """
        empty_state = self._read_empty_state()
        if empty_state is not None:
            # Quando nenhuma vulnerabilidade afeta a versão atual, o total
            # aparece no próprio texto do estado vazio e a tabela nem existe.
            match = TOTAL_VULNERABILITIES_PATTERN.search(empty_state)
            return 0, int(match.group(1)) if match else 0

        latest = self._count_vulnerability_rows()
        if not self._disable_latest_version_filter():
            logger.warning(
                "Não foi possível desligar o filtro de versão para %s; "
                "total de vulnerabilidades ficará vazio.",
                package_name,
            )
            return latest, None

        return latest, self._count_after_filter_removal(latest)

    def _read_empty_state(self) -> Optional[str]:
        try:
            return self._driver.find_element(By.CSS_SELECTOR, EMPTY_STATE_SELECTOR).text
        except NoSuchElementException:
            return None

    def _count_vulnerability_rows(self) -> int:
        return len(self._driver.find_elements(By.CSS_SELECTOR, VULNERABILITY_ROW_SELECTOR))

    def _disable_latest_version_filter(self) -> bool:
        """Desmarca o filtro de vulnerabilidades da versão atual."""
        try:
            checkbox = self._driver.find_element(By.CSS_SELECTOR, FILTER_CHECKBOX_SELECTOR)
            # O atributo HTML `checked` guarda apenas o estado inicial; o
            # estado real vive na propriedade do DOM, que is_selected() lê.
            if not checkbox.is_selected():
                return True

            # O clique vai no próprio input: ele fica sobreposto ao elemento
            # visual do toggle, então clicar no `.toggle__toggle` é recusado.
            checkbox.click()
            return True
        except (NoSuchElementException, ElementClickInterceptedException) as exc:
            logger.warning("Filtro de versão não pôde ser alterado: %s", exc)
            return False

    def _count_after_filter_removal(self, latest_count: int) -> int:
        """Conta as linhas depois de remover o filtro.

        Remover o filtro só pode revelar mais linhas, nunca menos. Se a
        contagem não crescer dentro do tempo limite, é porque todas as
        vulnerabilidades do pacote afetam a versão mais recente.
        """
        try:
            WebDriverWait(self._driver, self._filter_timeout).until(
                lambda _: self._count_vulnerability_rows() > latest_count
            )
        except TimeoutException:
            return latest_count
        return self._count_vulnerability_rows()
