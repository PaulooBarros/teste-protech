"""Testes da orquestração da aplicação."""

import logging

import pytest

from src.main import load_dependencies

logger = logging.getLogger("testes")


def write(tmp_path, filename, content):
    path = tmp_path / filename
    path.write_text(content, encoding="utf-8")
    return path


class TestEscolhaDoParser:
    def test_le_requirements_txt(self, tmp_path):
        path = write(tmp_path, "requirements.txt", "flask==3.1.3\n")

        assert load_dependencies(path, logger) == {"flask": "==3.1.3"}

    @pytest.mark.parametrize(
        "filename",
        ["requirements-dev.txt", "requirements_prod.txt", "reqs.txt", "REQUIREMENTS.TXT"],
    )
    def test_aceita_outros_nomes_de_arquivo_txt(self, tmp_path, filename):
        """O parser é escolhido pela extensão: exigir o nome exato quebraria
        convenções comuns como `requirements-dev.txt`."""
        path = write(tmp_path, filename, "flask==3.1.3\n")

        assert load_dependencies(path, logger) == {"flask": "==3.1.3"}

    def test_le_pyproject_toml(self, tmp_path):
        conteudo = '[project]\ndependencies = ["flask>=3.0"]\n'
        path = write(tmp_path, "pyproject.toml", conteudo)

        assert load_dependencies(path, logger) == {"flask": ">=3.0"}

    def test_aceita_outros_nomes_de_arquivo_toml(self, tmp_path):
        conteudo = '[project]\ndependencies = ["flask>=3.0"]\n'
        path = write(tmp_path, "config.toml", conteudo)

        assert load_dependencies(path, logger) == {"flask": ">=3.0"}


class TestEntradasInvalidas:
    def test_arquivo_inexistente_encerra_com_mensagem(self, tmp_path):
        path = tmp_path / "nao-existe.txt"

        with pytest.raises(SystemExit, match="não encontrado"):
            load_dependencies(path, logger)

    @pytest.mark.parametrize("filename", ["deps.json", "deps.yaml", "deps"])
    def test_formato_nao_suportado_encerra_com_mensagem(self, tmp_path, filename):
        path = write(tmp_path, filename, "flask==3.1.3\n")

        with pytest.raises(SystemExit, match="Formato não suportado"):
            load_dependencies(path, logger)
