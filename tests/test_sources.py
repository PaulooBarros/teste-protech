"""Testes da leitura do arquivo de dependências, local ou remoto."""

from unittest.mock import Mock, patch

import pytest
import requests

from src.sources import MAX_SIZE_BYTES, SourceError, is_url, read_source


def fake_response(text="flask==3.1.3\n"):
    response = Mock()
    response.text = text
    response.content = text.encode("utf-8")
    response.raise_for_status.return_value = None
    return response


def baixar(url, text="flask==3.1.3\n"):
    with patch("src.sources.requests.get", return_value=fake_response(text)) as get:
        return read_source(url), get


class TestReconhecimentoDeUrl:
    @pytest.mark.parametrize(
        "location",
        [
            "https://raw.githubusercontent.com/org/repo/main/requirements.txt",
            "http://exemplo.com/requirements.txt",
        ],
    )
    def test_reconhece_endereco_web(self, location):
        assert is_url(location) is True

    @pytest.mark.parametrize(
        "location",
        [
            "requirements.txt",
            "C:/projetos/app/requirements.txt",
            "/home/paulo/app/pyproject.toml",
            "./requirements.txt",
        ],
    )
    def test_caminho_local_nao_e_url(self, location):
        assert is_url(location) is False


class TestLeituraLocal:
    def test_le_o_conteudo_do_arquivo(self, tmp_path):
        arquivo = tmp_path / "requirements.txt"
        arquivo.write_text("flask==3.1.3\n", encoding="utf-8")

        assert read_source(arquivo).text == "flask==3.1.3\n"

    def test_informa_a_extensao(self, tmp_path):
        arquivo = tmp_path / "pyproject.toml"
        arquivo.write_text("", encoding="utf-8")

        assert read_source(arquivo).suffix == ".toml"

    def test_extensao_em_maiusculas_e_normalizada(self, tmp_path):
        arquivo = tmp_path / "REQUIREMENTS.TXT"
        arquivo.write_text("", encoding="utf-8")

        assert read_source(arquivo).suffix == ".txt"

    def test_arquivo_inexistente_falha_com_mensagem_clara(self, tmp_path):
        with pytest.raises(SourceError, match="não encontrado"):
            read_source(tmp_path / "nao-existe.txt")


class TestLeituraRemota:
    def test_baixa_o_conteudo(self):
        url = "https://exemplo.com/requirements.txt"
        source, _ = baixar(url)

        assert source.text == "flask==3.1.3\n"
        assert source.origin == url

    def test_extensao_vem_do_caminho_da_url(self):
        source, _ = baixar("https://exemplo.com/projeto/pyproject.toml")

        assert source.suffix == ".toml"

    def test_ignora_a_query_string_ao_ler_a_extensao(self):
        """`.../requirements.txt?raw=1` continua sendo um `.txt`."""
        source, _ = baixar("https://exemplo.com/requirements.txt?raw=1&token=abc")

        assert source.suffix == ".txt"

    @pytest.mark.parametrize(
        "erro",
        [
            requests.Timeout("tempo esgotado"),
            requests.ConnectionError("sem conexão"),
            requests.HTTPError("404 Not Found"),
        ],
    )
    def test_falha_de_rede_vira_mensagem_clara(self, erro):
        with (
            patch("src.sources.requests.get", side_effect=erro),
            pytest.raises(SourceError, match="Não foi possível baixar"),
        ):
            read_source("https://exemplo.com/requirements.txt")

    def test_recusa_arquivo_grande_demais(self):
        """Um endereço apontando para um arquivo enorme travaria a execução."""
        gigante = "x" * (MAX_SIZE_BYTES + 1)

        with (
            patch("src.sources.requests.get", return_value=fake_response(gigante)),
            pytest.raises(SourceError, match="acima do limite"),
        ):
            read_source("https://exemplo.com/requirements.txt")
