"""Testes das regras de extração do scraper que não dependem do navegador."""

import pytest

from src.snyk_scraper import (
    SCORE_PATTERN,
    TOTAL_VULNERABILITIES_PATTERN,
    SnykPackageData,
    SnykScraper,
)


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
