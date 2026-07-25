"""Логирование использования приложения в analytics.csv через GitHub API."""

import base64
import uuid
from datetime import date, datetime

import requests
import streamlit as st

GITHUB_REPO_OWNER = "IliaKurdukov"
GITHUB_REPO_NAME = "the_security_curves"
GITHUB_BRANCH = "main"
CSV_SEPARATOR = ";"
ANALYTICS_PATH = "analytics.csv"

# Файлы, которые не должны попадать в аналитику
TEST_FILES = ["тест.xlsx"]


def get_session_id():
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    return st.session_state.session_id


def get_github_token():
    try:
        return st.secrets.get("github_token", None)
    except Exception:
        return None


def get_csv_from_github(token):
    """Получает CSV файл с GitHub. Возвращает (sha, content) или (None, None)."""
    try:
        url = (
            f"https://api.github.com/repos/{GITHUB_REPO_OWNER}/"
            f"{GITHUB_REPO_NAME}/contents/{ANALYTICS_PATH}"
        )
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }

        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return None, None

        file_data = response.json()
        content = base64.b64decode(file_data["content"]).decode("utf-8")
        sha = file_data["sha"]
        return sha, content
    except Exception:
        return None, None


def save_to_github(token, sha, content):
    """Сохраняет CSV файл на GitHub."""
    try:
        url = (
            f"https://api.github.com/repos/{GITHUB_REPO_OWNER}/"
            f"{GITHUB_REPO_NAME}/contents/{ANALYTICS_PATH}"
        )
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }

        data = {
            "message": f"Update analytics: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
            "sha": sha,
            "branch": GITHUB_BRANCH,
        }

        response = requests.put(url, headers=headers, json=data)
        return response.status_code in [200, 201]
    except Exception:
        return False


def is_test_file(filename):
    """Проверяет, является ли файл тестовым."""
    if not filename:
        return False
    return any(test_file.lower() in filename.lower() for test_file in TEST_FILES)


def format_list_for_csv(items):
    """Форматирует список в строку для CSV."""
    if not items:
        return "[]"
    return "[" + ", ".join(str(item).replace('"', '""') for item in items) + "]"


def parse_list_from_csv(csv_string):
    """Парсит список из CSV строки."""
    if not csv_string or csv_string == "[]":
        return []
    try:
        items = csv_string[1:-1].split(", ")
        return [item.strip().replace('""', '"') for item in items if item.strip()]
    except Exception:
        return []


def log_analytics(uploaded_file=None, distributions_selected=None, custom_ensurence_value=None):
    """Создает/обновляет запись в аналитике — только последний выбор."""
    try:
        token = get_github_token()
        if not token or not uploaded_file:
            return False

        if is_test_file(uploaded_file.name):
            return False

        session_id = get_session_id()

        sha, content = get_csv_from_github(token)
        if sha is None:
            return False

        lines = content.split("\n")
        if not lines or len(lines) < 2:
            headers = (
                f"date{CSV_SEPARATOR}time{CSV_SEPARATOR}session_id{CSV_SEPARATOR}"
                f"file_name{CSV_SEPARATOR}file_size{CSV_SEPARATOR}file_rows{CSV_SEPARATOR}"
                f"distributions_selected{CSV_SEPARATOR}distributions_count{CSV_SEPARATOR}"
                f"custom_ensurence_value"
            )
            lines = [headers, ""]

        session_found = False
        session_line_index = None
        for i in range(1, len(lines)):
            if lines[i].strip() and session_id in lines[i]:
                session_found = True
                session_line_index = i
                break

        now = datetime.now()
        date_str = date.today().isoformat()
        time_str = now.strftime("%H:%M:%S")

        if session_found:
            parts = lines[session_line_index].split(CSV_SEPARATOR)

            parts[0] = date_str
            parts[1] = time_str

            if distributions_selected is not None:
                parts[6] = format_list_for_csv(list(distributions_selected))
                parts[7] = str(len(distributions_selected))

            if custom_ensurence_value is not None:
                current_values = parse_list_from_csv(parts[8]) if len(parts) > 8 else []
                custom_float = float(custom_ensurence_value)

                if abs(custom_float - 0.001) > 0.0001:
                    current_floats = []
                    for v in current_values:
                        try:
                            current_floats.append(float(v))
                        except Exception:
                            pass

                    if custom_float not in current_floats:
                        current_values.append(str(custom_float))

                parts[8] = format_list_for_csv(current_values)

            lines[session_line_index] = CSV_SEPARATOR.join(parts)

        else:
            dist_list = list(distributions_selected) if distributions_selected else []

            custom_values = []
            if custom_ensurence_value is not None:
                custom_float = float(custom_ensurence_value)
                if abs(custom_float - 0.001) > 0.0001:
                    custom_values = [str(custom_float)]

            new_line_parts = [
                date_str,
                time_str,
                session_id,
                uploaded_file.name,
                str(len(uploaded_file.getvalue())),
                "None",
                format_list_for_csv(dist_list),
                str(len(dist_list)),
                format_list_for_csv(custom_values),
            ]

            new_line = CSV_SEPARATOR.join(new_line_parts)

            if lines[-1] == "":
                lines[-1] = new_line
            else:
                lines.append(new_line)
            lines.append("")

        new_content = "\n".join(lines)
        return save_to_github(token, sha, new_content)

    except Exception:
        return False


def update_analytics_file_rows(file_rows):
    """Обновляет количество строк в файле для текущей сессии."""
    try:
        token = get_github_token()
        if not token:
            return False

        session_id = get_session_id()

        sha, content = get_csv_from_github(token)
        if sha is None:
            return False

        lines = content.split("\n")
        for i in range(1, len(lines)):
            if lines[i].strip() and session_id in lines[i]:
                parts = lines[i].split(CSV_SEPARATOR)
                if len(parts) > 5:
                    if len(parts) > 3 and is_test_file(parts[3]):
                        lines.pop(i)
                    else:
                        parts[5] = str(file_rows)
                        lines[i] = CSV_SEPARATOR.join(parts)
                    break

        new_content = "\n".join(lines)
        return save_to_github(token, sha, new_content)

    except Exception:
        return False
