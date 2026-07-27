"""Testes da configuração de logs."""

import logging
from logging.handlers import RotatingFileHandler

import pytest

from src.logger import BACKUP_COUNT, LOGGER_NAME, MAX_BYTES, configure_logger


@pytest.fixture(autouse=True)
def limpa_handlers():
    """Fecha os arquivos abertos depois de cada teste.

    Sem isso, o Windows recusa apagar o diretório temporário enquanto o
    arquivo de log continuar aberto.
    """
    yield
    logger = logging.getLogger(LOGGER_NAME)
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)


def handlers_de(logger, tipo):
    return [handler for handler in logger.handlers if isinstance(handler, tipo)]


class TestGravacaoEmArquivo:
    def test_cria_o_arquivo_de_log(self, tmp_path):
        destino = tmp_path / "execucao.log"
        logger = configure_logger(log_file=destino)
        logger.info("mensagem de teste")

        assert destino.exists()
        assert "mensagem de teste" in destino.read_text(encoding="utf-8")

    def test_cria_o_diretorio_quando_nao_existe(self, tmp_path):
        destino = tmp_path / "logs" / "sub" / "execucao.log"
        configure_logger(log_file=destino).info("mensagem")

        assert destino.exists()

    def test_grava_acentos_corretamente(self, tmp_path):
        """No Windows, o padrão do sistema corromperia os acentos."""
        destino = tmp_path / "execucao.log"
        configure_logger(log_file=destino).info("6 dependências encontradas na versão")

        assert "dependências encontradas na versão" in destino.read_text(encoding="utf-8")

    def test_log_file_none_desliga_a_gravacao(self, tmp_path):
        logger = configure_logger(log_file=None)

        assert handlers_de(logger, RotatingFileHandler) == []

    def test_configura_a_rotacao(self, tmp_path):
        logger = configure_logger(log_file=tmp_path / "execucao.log")
        arquivo = handlers_de(logger, RotatingFileHandler)[0]

        assert arquivo.maxBytes == MAX_BYTES
        assert arquivo.backupCount == BACKUP_COUNT


class TestNiveis:
    def test_arquivo_guarda_debug(self, tmp_path):
        """O arquivo serve para diagnóstico: precisa do detalhe completo."""
        destino = tmp_path / "execucao.log"
        configure_logger(log_file=destino).debug("detalhe de depuração")

        assert "detalhe de depuração" in destino.read_text(encoding="utf-8")

    def test_console_omite_debug_por_padrao(self, tmp_path):
        logger = configure_logger(log_file=tmp_path / "execucao.log")
        console = handlers_de(logger, logging.StreamHandler)[0]

        assert console.level == logging.INFO

    def test_verbose_mostra_debug_no_console(self, tmp_path):
        logger = configure_logger(log_file=tmp_path / "execucao.log", verbose=True)
        console = handlers_de(logger, logging.StreamHandler)[0]

        assert console.level == logging.DEBUG


class TestRobustez:
    def test_nao_duplica_saidas_ao_reconfigurar(self, tmp_path):
        """Chamar duas vezes não pode fazer cada mensagem aparecer em dobro."""
        destino = tmp_path / "execucao.log"
        configure_logger(log_file=destino)
        logger = configure_logger(log_file=destino)

        assert len(logger.handlers) == 2  # console + arquivo

    def test_falha_ao_gravar_nao_interrompe_a_execucao(self, tmp_path):
        """Log é apoio: não conseguir gravá-lo não pode abortar o relatório."""
        # Um arquivo comum no lugar do diretório impede a criação do log.
        obstaculo = tmp_path / "logs"
        obstaculo.write_text("nao sou um diretorio", encoding="utf-8")

        logger = configure_logger(log_file=obstaculo / "execucao.log")

        assert handlers_de(logger, RotatingFileHandler) == []
        assert handlers_de(logger, logging.StreamHandler) != []
