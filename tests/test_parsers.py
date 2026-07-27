"""Testes da leitura de dependências."""

import pytest

from src.parsers import parse_pyproject, parse_requirements


def write(tmp_path, filename, content):
    path = tmp_path / filename
    path.write_text(content, encoding="utf-8")
    return path


class TestParseRequirements:
    def test_le_nome_e_versao(self, tmp_path):
        path = write(tmp_path, "requirements.txt", "flask==3.1.3\n")
        assert parse_requirements(path) == {"flask": "==3.1.3"}

    def test_dependencia_sem_versao_fica_none(self, tmp_path):
        path = write(tmp_path, "requirements.txt", "openpyxl\n")
        assert parse_requirements(path) == {"openpyxl": None}

    @pytest.mark.parametrize(
        "linha, esperado",
        [
            ("flask>=3.0", ">=3.0"),
            ("flask<=3.0", "<=3.0"),
            ("flask~=3.0", "~=3.0"),
            ("flask!=3.0", "!=3.0"),
            ("flask>3.0,<4.0", ">3.0,<4.0"),
        ],
    )
    def test_preserva_o_especificador_completo(self, tmp_path, linha, esperado):
        path = write(tmp_path, "requirements.txt", f"{linha}\n")
        assert parse_requirements(path) == {"flask": esperado}

    def test_ignora_comentarios_e_linhas_em_branco(self, tmp_path):
        conteudo = "# um comentário\n\nflask==3.1.3\n\n# outro\n"
        path = write(tmp_path, "requirements.txt", conteudo)
        assert parse_requirements(path) == {"flask": "==3.1.3"}

    def test_remove_comentario_no_fim_da_linha(self, tmp_path):
        path = write(tmp_path, "requirements.txt", "flask==3.1.3  # framework web\n")
        assert parse_requirements(path) == {"flask": "==3.1.3"}

    def test_descarta_extras(self, tmp_path):
        path = write(tmp_path, "requirements.txt", "requests[security,socks]>=2.31.0\n")
        assert parse_requirements(path) == {"requests": ">=2.31.0"}

    def test_descarta_marcador_de_ambiente(self, tmp_path):
        path = write(tmp_path, "requirements.txt", 'urllib3<2.0 ; python_version < "3.9"\n')
        assert parse_requirements(path) == {"urllib3": "<2.0"}

    def test_normaliza_espacos_no_especificador(self, tmp_path):
        path = write(tmp_path, "requirements.txt", "selenium >= 4.17.0\n")
        assert parse_requirements(path) == {"selenium": ">=4.17.0"}

    @pytest.mark.parametrize(
        "linha",
        ["-r outro.txt", "-e .", "--index-url https://pypi.org/simple", "--no-binary :all:"],
    )
    def test_ignora_linhas_de_opcao(self, tmp_path, linha):
        path = write(tmp_path, "requirements.txt", f"{linha}\nflask==3.1.3\n")
        assert parse_requirements(path) == {"flask": "==3.1.3"}

    def test_aceita_ponto_e_hifen_no_nome(self, tmp_path):
        conteudo = "zope.interface~=5.0\npytest-cov==4.0\n"
        path = write(tmp_path, "requirements.txt", conteudo)
        assert parse_requirements(path) == {"zope.interface": "~=5.0", "pytest-cov": "==4.0"}

    def test_arquivo_vazio_devolve_dicionario_vazio(self, tmp_path):
        path = write(tmp_path, "requirements.txt", "")
        assert parse_requirements(path) == {}


class TestParsePyproject:
    def test_le_formato_pep_621(self, tmp_path):
        conteudo = """
[project]
name = "exemplo"
dependencies = ["flask>=3.0", "requests==2.31.0", "openpyxl"]
"""
        path = write(tmp_path, "pyproject.toml", conteudo)
        assert parse_pyproject(path) == {
            "flask": ">=3.0",
            "requests": "==2.31.0",
            "openpyxl": None,
        }

    def test_le_formato_poetry(self, tmp_path):
        conteudo = """
[tool.poetry.dependencies]
flask = "^3.0"
selenium = { version = "^4.17" }
"""
        path = write(tmp_path, "pyproject.toml", conteudo)
        assert parse_pyproject(path) == {"flask": "^3.0", "selenium": "^4.17"}

    def test_ignora_a_versao_do_python_do_poetry(self, tmp_path):
        conteudo = """
[tool.poetry.dependencies]
python = "^3.11"
flask = "^3.0"
"""
        path = write(tmp_path, "pyproject.toml", conteudo)
        assert parse_pyproject(path) == {"flask": "^3.0"}

    def test_dependencia_poetry_sem_versao_explicita(self, tmp_path):
        conteudo = """
[tool.poetry.dependencies]
flask = { git = "https://github.com/pallets/flask.git" }
"""
        path = write(tmp_path, "pyproject.toml", conteudo)
        assert parse_pyproject(path) == {"flask": None}

    def test_combina_os_dois_formatos(self, tmp_path):
        conteudo = """
[project]
dependencies = ["flask>=3.0"]

[tool.poetry.dependencies]
selenium = "^4.17"
"""
        path = write(tmp_path, "pyproject.toml", conteudo)
        assert parse_pyproject(path) == {"flask": ">=3.0", "selenium": "^4.17"}

    def test_sem_secao_de_dependencias(self, tmp_path):
        path = write(tmp_path, "pyproject.toml", '[project]\nname = "exemplo"\n')
        assert parse_pyproject(path) == {}
