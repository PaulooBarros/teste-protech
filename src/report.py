from datetime import datetime
from pathlib import Path
from typing import List

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from src.models import DependencyInfo


def build_report(dependencies: List[DependencyInfo], destination: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Dependências"

    headers = [
        "Nome",
        "Versão requisitada",
        "Última versão PyPI",
        "Descrição",
        "Licença",
        "Última publicação",
        "Score Snyk",
        "Vulnerabilidades (total)",
        "Vulnerabilidades (versão atual)",
        "Notas",
    ]

    sheet.append(headers)
    for index, dependency in enumerate(dependencies, start=2):
        sheet.append(dependency.to_row())
        _apply_score_style(sheet, index, dependency.snyk_score)

    _style_header(sheet)
    _adjust_columns(sheet)
    workbook.save(destination)


def _style_header(sheet) -> None:
    bold = Font(bold=True)
    for cell in sheet[1]:
        cell.font = bold


def _apply_score_style(sheet, row_index: int, score) -> None:
    if score is None:
        return

    try:
        numeric_score = float(score)
    except (TypeError, ValueError):
        return

    if numeric_score < 65:
        fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
        for cell in sheet[row_index]:
            cell.fill = fill


def _adjust_columns(sheet) -> None:
    for column in sheet.columns:
        max_length = 0
        column_letter = get_column_letter(column[0].column)
        for cell in column:
            value = str(cell.value or "")
            max_length = max(max_length, len(value))
        sheet.column_dimensions[column_letter].width = min(max_length + 2, 50)
