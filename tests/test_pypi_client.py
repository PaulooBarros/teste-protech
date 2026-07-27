"""Testes do cliente da API pública do PyPI."""

from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
import requests

from src.pypi_client import fetch_package_info


def fake_response(payload):
    """Simula uma resposta bem-sucedida da API."""
    response = Mock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


def fetch_with_payload(payload, package_name="flask"):
    with patch("src.pypi_client.requests.get", return_value=fake_response(payload)) as get:
        resultado = fetch_package_info(package_name)
    return resultado, get


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
        with patch("src.pypi_client.requests.get", side_effect=erro):
            resultado = fetch_package_info("inexistente")

        assert resultado == {
            "pypi_version": None,
            "description": None,
            "license": None,
            "last_release_date": None,
        }
