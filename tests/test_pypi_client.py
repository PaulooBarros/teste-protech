"""Testes do cliente da API pública do PyPI."""

from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
import requests

from src.pypi_client import PyPiClient


def fake_response(payload):
    """Simula uma resposta bem-sucedida da API."""
    response = Mock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


def fetch_with_payload(payload, package_name="flask"):
    """Consulta o cliente com uma sessão falsa, sem tocar na rede."""
    session = Mock()
    session.get.return_value = fake_response(payload)

    resultado = PyPiClient(session=session).fetch(package_name)
    return resultado, session.get


def fetch_with_error(erro, package_name="inexistente"):
    session = Mock()
    session.get.side_effect = erro

    return PyPiClient(session=session).fetch(package_name)


class TestCamposBasicos:
    def test_extrai_versao_e_descricao(self):
        payload = {"info": {"version": "3.1.3", "summary": "Um framework web"}, "releases": {}}
        resultado, _ = fetch_with_payload(payload)

        assert resultado["pypi_version"] == "3.1.3"
        assert resultado["description"] == "Um framework web"

    def test_consulta_a_url_do_pacote(self):
        _, get = fetch_with_payload({"info": {}, "releases": {}}, package_name="requests")
        url = get.call_args.args[0]

        assert url == "https://pypi.org/pypi/requests/json"

    def test_campos_ausentes_viram_none(self):
        resultado, _ = fetch_with_payload({"info": {}, "releases": {}})

        assert resultado["pypi_version"] is None
        assert resultado["description"] is None
        assert resultado["license"] is None


class TestLicenca:
    """A licença tem três fontes possíveis, testadas em ordem de prioridade."""

    def test_prefere_license_expression(self):
        info = {
            "license_expression": "BSD-3-Clause",
            "license": "BSD",
            "classifiers": ["License :: OSI Approved :: MIT License"],
        }
        resultado, _ = fetch_with_payload({"info": info, "releases": {}})

        assert resultado["license"] == "BSD-3-Clause"

    def test_usa_o_campo_legado_quando_nao_ha_expressao(self):
        info = {"license": "Public domain"}
        resultado, _ = fetch_with_payload({"info": info, "releases": {}})

        assert resultado["license"] == "Public domain"

    def test_recorre_aos_classificadores(self):
        info = {
            "license": "",
            "classifiers": ["Programming Language :: Python", "License :: OSI Approved :: MIT License"],
        }
        resultado, _ = fetch_with_payload({"info": info, "releases": {}})

        assert resultado["license"] == "MIT License"

    def test_descarta_texto_integral_da_licenca(self):
        """Alguns pacotes despejam a licença inteira no campo `license`."""
        info = {
            "license": "Copyright (c) 2024. " + "Permission is hereby granted, free of charge. " * 10,
            "classifiers": ["License :: OSI Approved :: Apache Software License"],
        }
        resultado, _ = fetch_with_payload({"info": info, "releases": {}})

        assert resultado["license"] == "Apache Software License"

    def test_sem_nenhuma_fonte_devolve_none(self):
        resultado, _ = fetch_with_payload({"info": {"classifiers": []}, "releases": {}})

        assert resultado["license"] is None


class TestDataDaUltimaPublicacao:
    def test_usa_a_publicacao_mais_recente(self):
        releases = {
            "1.0": [{"upload_time_iso_8601": "2020-01-01T00:00:00Z"}],
            "2.0": [{"upload_time_iso_8601": "2024-06-15T12:30:00Z"}],
            "1.5": [{"upload_time_iso_8601": "2022-03-10T00:00:00Z"}],
        }
        resultado, _ = fetch_with_payload({"info": {}, "releases": releases})

        assert resultado["last_release_date"] == datetime(2024, 6, 15, 12, 30, tzinfo=timezone.utc)

    def test_ignora_datas_em_formato_invalido(self):
        releases = {
            "1.0": [{"upload_time_iso_8601": "data-invalida"}],
            "2.0": [{"upload_time_iso_8601": "2024-06-15T12:30:00Z"}],
        }
        resultado, _ = fetch_with_payload({"info": {}, "releases": releases})

        assert resultado["last_release_date"] == datetime(2024, 6, 15, 12, 30, tzinfo=timezone.utc)

    def test_sem_releases_devolve_none(self):
        resultado, _ = fetch_with_payload({"info": {}, "releases": {}})

        assert resultado["last_release_date"] is None


class TestVulnerabilidades:
    """Contagem vinda da base OSV, usada para cruzar com os dados do Snyk."""

    def test_conta_as_vulnerabilidades_reportadas(self):
        payload = {
            "info": {},
            "releases": {},
            "vulnerabilities": [
                {"id": "PYSEC-2017-94", "aliases": ["CVE-2013-7459"]},
                {"id": "PYSEC-2013-25", "aliases": []},
            ],
        }
        resultado, _ = fetch_with_payload(payload)

        assert resultado["vulnerabilities"] == 2

    def test_lista_vazia_significa_nenhuma_vulnerabilidade(self):
        """Zero é uma resposta, diferente de dado ausente."""
        resultado, _ = fetch_with_payload({"info": {}, "releases": {}, "vulnerabilities": []})

        assert resultado["vulnerabilities"] == 0

    def test_campo_ausente_devolve_none(self):
        """Sem o campo, não sabemos a contagem — não é o mesmo que zero."""
        resultado, _ = fetch_with_payload({"info": {}, "releases": {}})

        assert resultado["vulnerabilities"] is None

    @pytest.mark.parametrize("valor", [None, "3", 3, {}])
    def test_formato_inesperado_devolve_none(self, valor):
        resultado, _ = fetch_with_payload({"info": {}, "releases": {}, "vulnerabilities": valor})

        assert resultado["vulnerabilities"] is None


class TestRepeticaoAutomatica:
    """Falhas temporárias da API não podem virar buraco no relatório."""

    def test_configura_repeticao_para_falhas_temporarias(self):
        adaptador = PyPiClient(attempts=3, backoff=0.5)._session.get_adapter("https://pypi.org")
        politica = adaptador.max_retries

        assert politica.total == 2  # 3 tentativas = 1 original + 2 repetições
        assert politica.backoff_factor == 0.5

    @pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
    def test_repete_nos_status_temporarios(self, status):
        adaptador = PyPiClient()._session.get_adapter("https://pypi.org")

        assert status in adaptador.max_retries.status_forcelist

    def test_nao_repete_em_404(self):
        """Pacote inexistente não passa a existir por insistência."""
        adaptador = PyPiClient()._session.get_adapter("https://pypi.org")

        assert 404 not in adaptador.max_retries.status_forcelist


class TestTratamentoDeErros:
    @pytest.mark.parametrize(
        "erro",
        [
            requests.Timeout("tempo esgotado"),
            requests.ConnectionError("sem conexão"),
            requests.HTTPError("404 Not Found"),
        ],
    )
    def test_falhas_de_rede_devolvem_campos_vazios(self, erro):
        """Uma falha na API não pode interromper a geração do relatório."""
        resultado = fetch_with_error(erro)

        assert resultado == {
            "pypi_version": None,
            "description": None,
            "license": None,
            "last_release_date": None,
            "vulnerabilities": None,
        }

    def test_retorno_de_falha_tem_as_mesmas_chaves_do_sucesso(self):
        """Chaves diferentes entre sucesso e falha quebrariam quem consome."""
        sucesso, _ = fetch_with_payload({"info": {}, "releases": {}, "vulnerabilities": []})
        falha = fetch_with_error(requests.Timeout())

        assert sucesso.keys() == falha.keys()
