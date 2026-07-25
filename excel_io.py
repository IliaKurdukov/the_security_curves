"""Чтение загруженных Excel-файлов."""

import pandas as pd

# xlrd — старый .xls; openpyxl — .xlsx / .xlsm
_ENGINES = {
    "xls": "xlrd",
    "xlsx": "openpyxl",
    "xlsm": "openpyxl",
}


def read_excel(uploaded_file):
    """Читает Excel по расширению файла. Движки уже в requirements.txt."""
    ext = uploaded_file.name.rsplit(".", 1)[-1].lower()
    engine = _ENGINES.get(ext)
    if engine is None:
        raise ValueError(f"Неподдерживаемый формат: .{ext}")
    return pd.read_excel(uploaded_file, engine=engine)
