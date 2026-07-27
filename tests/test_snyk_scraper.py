"""Testes das regras de extração do scraper que não dependem do navegador."""

from unittest.mock import Mock, patch

import pytest
from selenium.common.exceptions import TimeoutException, WebDriverException

from src.snyk_scraper import (
    SCORE_PATTERN,
    TOTAL_VULNERABILITIES_PATTERN,
    SnykPackageData,
    SnykScraper,
)


def fake_driver(title="flask | Snyk"):
    """Navegador simulado: evita abrir o Chrome nos testes."""
    driver = Mock()
    driver.title = title
    return driver


class TestNormalizacaoDeNome:
    """Nomes vêm do arquivo de dependências e precisam virar URL válida."""

    @pytest.mark.parametrize(
        "declarado, esperado",
        [
            ("Flask", "flask"),
            ("FLASK", "flask"),
            ("flask", "flask"),
            ("zope.interface", "zope-interface"),
            ("pytest_cov", "pytest-cov"),
            ("Pillow", "pillow"),
            ("ruamel.yaml.clib", "ruamel-yaml-clib"),
            ("foo___bar", "foo-bar"),
        ],
    )
    def test_normaliza_conforme_a_pep_503(self, declarado, esperado):
        assert SnykScraper._normalize_name(declarado) == esperado


class TestLeituraDoScore:
    @pytest.mark.parametrize(
        "texto, esperado",
        [("90/100", "90"), ("44/100", "44"), ("0/100", "0"), ("100/100", "100")],
    )
    def test_extrai_o_score(self, texto, esperado):
        assert SCORE_PATTERN.search(texto).group(1) == esperado

    def test_tolera_espacos_ao_redor_da_barra(self):
        assert SCORE_PATTERN.search("72 / 100").group(1) == "72"

    def test_texto_sem_score_nao_casa(self):
        assert SCORE_PATTERN.search("Package Health Score") is None


class TestContagemTotalDeVulnerabilidades:
    """O total aparece no texto exibido quando a versão atual está limpa."""

    def test_extrai_o_total_do_texto(self):
        texto = "There are 6 total vulnerabilities, but none affect the latest version (3.1.3)"

        assert TOTAL_VULNERABILITIES_PATTERN.search(texto).group(1) == "6"

    def test_reconhece_o_singular(self):
        texto = "There is 1 total vulnerability, but none affect the latest version (2.0)"

        assert TOTAL_VULNERABILITIES_PATTERN.search(texto).group(1) == "1"

    def test_texto_sem_contagem_nao_casa(self):
        assert TOTAL_VULNERABILITIES_PATTERN.search("No vulnerabilities found") is None


class TestSnykPackageData:
    def test_campos_comecam_vazios(self):
        """O resultado vazio é o que o scraper devolve quando a coleta falha."""
        dados = SnykPackageData()

        assert dados.score is None
        assert dados.vulnerabilities_total is None
        assert dados.vulnerabilities_latest is None


class TestCicloDeVida:
    def test_fetch_sem_navegador_iniciado_falha_explicitamente(self):
        scraper = SnykScraper()

        with pytest.raises(RuntimeError, match="navegador não foi iniciado"):
            scraper.fetch("flask")


class TestCarregamentoDaPagina:
    """Política de repetição: insistir só quando há chance de sucesso."""

    def test_pacote_ausente_do_catalogo_nao_e_repetido(self):
        """Repetir não faria o pacote passar a existir — seria só demora."""
        driver = fake_driver(title="Package not found | Snyk")
        scraper = SnykScraper(driver=driver, attempts=3, retry_wait=0)

        assert scraper.fetch("pacote-inexistente") == SnykPackageData()
        assert driver.get.call_count == 1

    def test_repete_quando_a_pagina_nao_carrega(self):
        driver = fake_driver()
        scraper = SnykScraper(driver=driver, attempts=3, retry_wait=0)

        with patch.object(SnykScraper, "_wait_for_package_page", side_effect=TimeoutException()):
            assert scraper.fetch("flask") == SnykPackageData()

        assert driver.get.call_count == 3

    def test_para_de_repetir_assim_que_a_pagina_carrega(self):
        driver = fake_driver()
        scraper = SnykScraper(driver=driver, attempts=3, retry_wait=0)
        tentativas = [TimeoutException(), None]

        with patch.object(SnykScraper, "_wait_for_package_page", side_effect=tentativas):
            with patch.object(SnykScraper, "_read_score", return_value=90):
                with patch.object(SnykScraper, "_read_vulnerability_counts", return_value=(0, 6)):
                    dados = scraper.fetch("flask")

        assert driver.get.call_count == 2
        assert dados == SnykPackageData(score=90, vulnerabilities_total=6, vulnerabilities_latest=0)

    def test_espera_cresce_a_cada_tentativa(self):
        """Espera progressiva: insistir de imediato tende a falhar de novo."""
        scraper = SnykScraper(driver=fake_driver(), attempts=4, retry_wait=2.0)

        with patch.object(SnykScraper, "_wait_for_package_page", side_effect=TimeoutException()):
            with patch("src.snyk_scraper.time.sleep") as sleep:
                scraper.fetch("flask")

        assert [chamada.args[0] for chamada in sleep.call_args_list] == [2.0, 4.0, 6.0]

    def test_falha_do_navegador_nao_e_repetida(self):
        """Navegador quebrado não se recupera sozinho entre tentativas."""
        driver = fake_driver()
        driver.get.side_effect = WebDriverException("sessão encerrada")
        scraper = SnykScraper(driver=driver, attempts=3, retry_wait=0)

        assert scraper.fetch("flask") == SnykPackageData()
        assert driver.get.call_count == 1
