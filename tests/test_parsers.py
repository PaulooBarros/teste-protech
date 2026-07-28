"""Testes da leitura de dependências.

Os parsers recebem texto, não caminho de arquivo, então os testes não
precisam criar arquivos temporários.
"""

import pytest

from src.parsers import parse_pyproject, parse_requirements


class TestParseRequirements:
    def test_le_nome_e_versao(self):
        assert parse_requirements("flask==3.1.3\n") == {"flask": "==3.1.3"}

    def test_dependencia_sem_versao_fica_none(self):
        assert parse_requirements("openpyxl\n") == {"openpyxl": None}

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
    def test_preserva_o_especificador_completo(self, linha, esperado):
        assert parse_requirements(linha) == {"flask": esperado}

    def test_ignora_comentarios_e_linhas_em_branco(self):
        conteudo = "# um comentário\n\nflask==3.1.3\n\n# outro\n"

        assert parse_requirements(conteudo) == {"flask": "==3.1.3"}

    def test_remove_comentario_no_fim_da_linha(self):
        assert parse_requirements("flask==3.1.3  # framework web") == {"flask": "==3.1.3"}

    def test_descarta_extras(self):
        assert parse_requirements("requests[security,socks]>=2.31.0") == {"requests": ">=2.31.0"}

    def test_descarta_marcador_de_ambiente(self):
        conteudo = 'urllib3<2.0 ; python_version < "3.9"'

        assert parse_requirements(conteudo) == {"urllib3": "<2.0"}

    def test_normaliza_espacos_no_especificador(self):
        assert parse_requirements("selenium >= 4.17.0") == {"selenium": ">=4.17.0"}

    @pytest.mark.parametrize(
        "linha",
        ["-r outro.txt", "-e .", "--index-url https://pypi.org/simple", "--no-binary :all:"],
    )
    def test_ignora_linhas_de_opcao(self, linha):
        assert parse_requirements(f"{linha}\nflask==3.1.3\n") == {"flask": "==3.1.3"}

    def test_aceita_ponto_e_hifen_no_nome(self):
        conteudo = "zope.interface~=5.0\npytest-cov==4.0\n"

        assert parse_requirements(conteudo) == {
            "zope.interface": "~=5.0",
            "pytest-cov": "==4.0",
        }

    def test_conteudo_vazio_devolve_dicionario_vazio(self):
        assert parse_requirements("") == {}

    def test_aceita_quebra_de_linha_do_windows(self):
        """Arquivos gravados no Windows usam CRLF."""
        assert parse_requirements("flask==3.1.3\r\nopenpyxl\r\n") == {
            "flask": "==3.1.3",
            "openpyxl": None,
        }


class TestParsePyproject:
    def test_le_formato_pep_621(self):
        conteudo = """
[project]
name = "exemplo"
dependencies = ["flask>=3.0", "requests==2.31.0", "openpyxl"]
"""

        assert parse_pyproject(conteudo) == {
            "flask": ">=3.0",
            "requests": "==2.31.0",
            "openpyxl": None,
        }

    def test_le_formato_poetry(self):
        conteudo = """
[tool.poetry.dependencies]
flask = "^3.0"
selenium = { version = "^4.17" }
"""

        assert parse_pyproject(conteudo) == {"flask": "^3.0", "selenium": "^4.17"}

    def test_ignora_a_versao_do_python_do_poetry(self):
        conteudo = """
[tool.poetry.dependencies]
python = "^3.11"
flask = "^3.0"
"""

        assert parse_pyproject(conteudo) == {"flask": "^3.0"}

    def test_dependencia_poetry_sem_versao_explicita(self):
        conteudo = """
[tool.poetry.dependencies]
flask = { git = "https://github.com/pallets/flask.git" }
"""

        assert parse_pyproject(conteudo) == {"flask": None}

    def test_combina_os_dois_formatos(self):
        conteudo = """
[project]
dependencies = ["flask>=3.0"]

[tool.poetry.dependencies]
selenium = "^4.17"
"""

        assert parse_pyproject(conteudo) == {"flask": ">=3.0", "selenium": "^4.17"}

    def test_sem_secao_de_dependencias(self):
        assert parse_pyproject('[project]\nname = "exemplo"\n') == {}
