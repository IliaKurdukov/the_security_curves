#!/usr/bin/env python3
"""
Скрипт для обновления аналитики в README.md
Создает графики с помощью matplotlib и сохраняет их как изображения
"""

import pandas as pd
from datetime import datetime, timedelta
import requests
import base64
import os
import re
from collections import Counter
import matplotlib.pyplot as plt
import matplotlib
import numpy as np
from pathlib import Path

# Настройка matplotlib для работы без GUI
matplotlib.use('Agg')

# Устанавливаем белый фон по умолчанию
plt.rcParams['figure.facecolor'] = 'white'
plt.rcParams['axes.facecolor'] = 'white'
plt.rcParams['savefig.facecolor'] = 'white'
plt.rcParams['savefig.edgecolor'] = 'none'

# Конфигурация
GITHUB_REPO_OWNER = "IliaKurdukov"
GITHUB_REPO_NAME = "the_security_curves"
CSV_SEPARATOR = ";"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GRAPHS_DIR = Path("graphs")

# Подписи графиков аналитики (ru / en)
ANALYTICS_LABELS = {
    "ru": {
        "daily_title": "Динамика количества использований по дням",
        "daily_regular": "Обычные загрузки",
        "daily_sample": "Тестовый файл",
        "daily_old_url": "Старый URL (заглушка)",
        "dist_title": "Самые распространенные распределения (кол-во использований)",
        "cloud_title": 'Самые частые названия файлов (кроме "Книга1" и "Лист Microsoft Excel")',
        "no_data": "*Нет данных для отображения*",
        "alt_daily": "Динамика использований",
        "alt_dist": "Популярные распределения",
        "alt_cloud": "Облако названий файлов",
        "date_fmt": "%d.%m",
    },
    "en": {
        "daily_title": "Daily usage over time",
        "daily_regular": "Regular uploads",
        "daily_sample": "Sample file",
        "daily_old_url": "Old URL (stub)",
        "dist_title": "Most used distributions (usage count)",
        "cloud_title": 'Most frequent upload filenames (excluding junk like "Book1")',
        "no_data": "*No data to display*",
        "alt_daily": "Daily usage",
        "alt_dist": "Popular distributions",
        "alt_cloud": "Filename word cloud",
        "date_fmt": "en_day_mon",
    },
}


def _graph_filename(stem: str, lang: str) -> Path:
    """ru → stem.png, en → stem_en.png"""
    suffix = "" if lang == "ru" else f"_{lang}"
    return GRAPHS_DIR / f"{stem}{suffix}.png"


def _dist_label(name: str, lang: str) -> str:
    """Локализованное имя распределения для графика."""
    try:
        import sys

        root = Path(__file__).resolve().parent.parent
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from i18n import TRANSLATIONS

        key = f"dist.{name}"
        return TRANSLATIONS.get(lang, {}).get(key) or TRANSLATIONS["ru"].get(key, name)
    except Exception:
        return name

# Должно совпадать с analytics.py
SAMPLE_FILE_NAMES = ["tsc_sample__daily_precip.xlsx"]
OLD_URL_STUB_NAME = "__old_url_stub__"
# Старое имя примера и файлы, полностью исключаемые из облака
EXCLUDED_WORDCLOUD_FILES = {
    "тест.xlsx",
    "суточные осадки.xlsx",
    "tsc_sample__daily_precip.xlsx",
}

# Целые имена-заглушки Excel / мусор (без расширения, lower)
JUNK_FILENAME_STEMS = {
    "книга1",
    "книга2",
    "книга3",
    "книга4",
    "книга5",
    "book1",
    "book2",
    "sheet1",
    "лист microsoft excel",
    "обработанный",
    "обработанные",
    "ряд",
    "данные",
    "файл",
    "new",
    "новый",
    "таблица",
    "без имени",
    "untitled",
}

# Токены, которые не несут смысла в названиях
JUNK_TOKENS = {
    "книга",
    "book",
    "sheet",
    "лист",
    "microsoft",
    "excel",
    "xlsx",
    "xls",
    "xlsm",
    "копия",
    "copy",
    "вариант",
    "версия",
    "temp",
    "tmp",
    "тест",
    "test",
    "sample",
    "пример",
    "для",
    "в",
    "и",
    "по",
    "на",
    "с",
    "из",
    "к",
    "от",
    "до",
    "без",
    "или",
    "the",
    "of",
    "and",
    "to",
    "a",
    "продолжение",
    "программа",
    "программу",
    "расчет",
    "расчёт",
    "расчеты",
    "расчёты",
    "расчётов",
    "расчетов",
    "данные",
    "файл",
    "таблица",
    "новый",
    "new",
    "обработанный",
    "обработанные",
    "ряд",
    "г",
    "р",
    "с",
    "пгт",
    "пос",
    "дер",
    "справка",
    "сводная",
    "даты",
    "дата",
    "характеристики",
    "характеристика",
    "малый",
    "большой",
    "koordinat",
    "координат",
    "координаты",
    "gidroposty",
    "os",
    "bez",
    "бд",
    "era",
    "epa",
    "ланд",
    "количество",
    "пос1",
}

# Matplotlib C0 + оттенки Blues (тёмная половина, чтобы читалось на белом)
_BLUE_CMAP = plt.colormaps.get_cmap("Blues") if hasattr(plt, "colormaps") else plt.cm.get_cmap("Blues")


def is_sample_file(filename):
    """Файл из кнопки «Загрузить тестовый файл»."""
    if filename is None or (isinstance(filename, float) and pd.isna(filename)):
        return False
    name = Path(str(filename)).name.lower()
    return any(item.lower() == name for item in SAMPLE_FILE_NAMES)


def is_old_url_stub(filename):
    """Визит на заглушку старого Streamlit URL."""
    if filename is None or (isinstance(filename, float) and pd.isna(filename)):
        return False
    return Path(str(filename)).name == OLD_URL_STUB_NAME


def _cyrillic_font_path():
    """Шрифт с кириллицей: DejaVu из matplotlib или системный."""
    import matplotlib as mpl

    candidates = [
        Path(mpl.get_data_path()) / "fonts" / "ttf" / "DejaVuSans.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/segoeui.ttf"),
    ]
    for path in candidates:
        if path.is_file():
            return str(path)
    return None


def _is_keyboard_mash(token):
    """ааааа / вввввв / asdf-подобное."""
    if len(token) < 3:
        return False
    if len(set(token)) == 1:
        return True
    # почти все символы одинаковые
    most = Counter(token).most_common(1)[0][1]
    return most / len(token) >= 0.75


def _is_junk_filename_stem(stem):
    s = stem.strip().lower()
    s = re.sub(r"\s*\(\d+\)\s*$", "", s).strip()
    if not s:
        return True
    if s in JUNK_FILENAME_STEMS:
        return True
    if re.fullmatch(r"книга\s*\d+(\s+\d+)*", s) or re.fullmatch(r"book\s*\d+", s):
        return True
    if s.startswith("лист microsoft excel"):
        return True
    if re.fullmatch(r"[\d\s._-]+", s):
        return True
    if _is_keyboard_mash(re.sub(r"[\s._-]+", "", s)):
        return True
    return False


def _is_junk_token(token):
    t = token.strip().lower()
    if len(t) < 2:
        return True
    if t in JUNK_TOKENS:
        return True
    if re.fullmatch(r"книга\d*", t) or re.fullmatch(r"book\d*", t):
        return True
    if re.fullmatch(r"\d+", t):
        return True
    if re.fullmatch(r"\d{4}", t):  # год
        return True
    if re.fullmatch(r"\d{4}\s*[-–—]\s*\d{4}", t):
        return True
    # коды вроде 11БД, 4сут
    if re.fullmatch(r"\d+[a-zа-яё]+", t, flags=re.IGNORECASE):
        return True
    if _is_keyboard_mash(t):
        return True
    return False


def extract_filename_tokens(filename):
    """Слова из имени файла для облака (без расширения и мусора)."""
    if filename is None or (isinstance(filename, float) and pd.isna(filename)):
        return []
    name = Path(str(filename)).name
    if name.lower() in {x.lower() for x in EXCLUDED_WORDCLOUD_FILES}:
        return []
    if is_sample_file(name):
        return []
    if is_old_url_stub(name):
        return []

    stem = Path(name).stem
    stem = re.sub(r"\s*[—–-]\s*копия\s*$", "", stem, flags=re.IGNORECASE)
    stem = re.sub(r"\s*\(\d+\)\s*$", "", stem).strip()
    if _is_junk_filename_stem(stem):
        return []

    # разделители → пробелы
    text = stem.replace("_", " ").replace("-", " ").replace("—", " ").replace("–", " ")
    text = text.replace(".", " ").replace(",", " ").replace("%", " ")
    text = re.sub(r"[()\[\]{}«»\"']", " ", text)
    parts = re.split(r"\s+", text)
    tokens = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # убрать ведущие нули у номеров вроде 01
        if re.fullmatch(r"0+\d+", part):
            continue
        if _is_junk_token(part):
            continue
        tokens.append(part)
    return tokens


def _blue_color_func(word, font_size, position, orientation, random_state=None, **kwargs):
    """Оттенки Blues на базе стандартной синей шкалы matplotlib."""
    if random_state is None:
        t = float(np.random.uniform(0.45, 0.95))
    else:
        t = float(random_state.uniform(0.45, 0.95))
    r, g, b, _ = _BLUE_CMAP(t)
    return f"rgb({int(r * 255)}, {int(g * 255)}, {int(b * 255)})"


def create_filename_wordcloud(df):
    """Облако слов по именам файлов — RU и EN (различаются подписи)."""
    try:
        from wordcloud import WordCloud
    except ImportError:
        return False

    df = df.copy()
    df = df[~df["file_name"].apply(is_sample_file)]
    df = df[~df["file_name"].apply(is_old_url_stub)]

    token_counts = Counter()
    for name in df["file_name"].dropna():
        for token in extract_filename_tokens(name):
            token_counts[token] += 1

    if not token_counts:
        return False

    folded = {}
    display = {}
    for token, count in token_counts.items():
        key = token.casefold()
        folded[key] = folded.get(key, 0) + count
        prev = display.get(key)
        if prev is None or (token[:1].isupper() and not prev[:1].isupper()):
            display[key] = token

    frequencies = {display[k]: v for k, v in folded.items()}
    if not frequencies:
        return False

    font_path = _cyrillic_font_path()
    GRAPHS_DIR.mkdir(exist_ok=True)
    ok = False
    for lang in ("ru", "en"):
        labels = ANALYTICS_LABELS[lang]
        wc = WordCloud(
            width=800,
            height=400,
            background_color="white",
            prefer_horizontal=0.9,
            max_words=80,
            relative_scaling=0.45,
            collocations=False,
            font_path=font_path,
            color_func=_blue_color_func,
            min_font_size=10,
        )
        wc.generate_from_frequencies(frequencies)

        fig, ax = plt.subplots(figsize=(8, 4))
        ax.imshow(wc, interpolation="bilinear")
        ax.axis("off")
        ax.set_title(labels["cloud_title"])
        plt.tight_layout()
        plt.savefig(
            _graph_filename("filename_wordcloud", lang),
            dpi=100,
            bbox_inches="tight",
            facecolor="white",
            edgecolor="none",
        )
        plt.close()
        ok = True
    return ok


def get_analytics_csv():
    """Загружает CSV с аналитикой из GitHub"""
    url = f"https://api.github.com/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/contents/analytics.csv"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return None
    
    file_data = response.json()
    content = base64.b64decode(file_data['content']).decode('utf-8')
    return content

def parse_distributions_list(dist_str):
    """Парсит строку с распределениями"""
    if not dist_str or dist_str == "[]":
        return []
    
    dist_str = dist_str.strip("[]'\"")
    if not dist_str:
        return []
    
    items = [item.strip().strip("'\"") for item in dist_str.split(",")]
    return [item for item in items if item]

def create_daily_activity_graph(df):
    """График активности по дням — RU и EN версии."""
    df = df.copy()
    df["datetime"] = pd.to_datetime(df["date"])

    yesterday = datetime.now() - timedelta(days=1)
    yesterday_date = yesterday.date()
    date_range = pd.date_range(end=yesterday_date, periods=15, freq="D")
    cutoff_date_dt = pd.Timestamp(yesterday - timedelta(days=14))

    recent = df[df["datetime"] >= cutoff_date_dt].copy()
    recent["_is_sample"] = recent["file_name"].apply(is_sample_file)
    recent["_is_stub"] = recent["file_name"].apply(is_old_url_stub)

    def counts_by_date(frame):
        if frame.empty:
            daily = pd.DataFrame(columns=["date", "count"])
        else:
            daily = frame.groupby("date").size().reset_index(name="count")
            daily["date"] = pd.to_datetime(daily["date"])
        full_dates = pd.DataFrame({"date": date_range})
        merged = pd.merge(full_dates, daily, on="date", how="left").fillna(0)
        return merged.sort_values("date")

    regular_counts = counts_by_date(
        recent[~recent["_is_sample"] & ~recent["_is_stub"]]
    )
    sample_counts = counts_by_date(recent[recent["_is_sample"]])
    stub_counts = counts_by_date(recent[recent["_is_stub"]])
    x = np.arange(len(regular_counts["date"]))
    y_max = max(
        regular_counts["count"].max(),
        sample_counts["count"].max(),
        stub_counts["count"].max(),
        5,
    )

    GRAPHS_DIR.mkdir(exist_ok=True)
    for lang in ("ru", "en"):
        labels = ANALYTICS_LABELS[lang]
        if labels["date_fmt"] == "en_day_mon":
            _en_mon = (
                "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
            )
            dates_display = [
                f"{d.day} {_en_mon[d.month - 1]}" for d in regular_counts["date"]
            ]
        else:
            dates_display = [
                d.strftime(labels["date_fmt"]) for d in regular_counts["date"]
            ]

        fig, ax = plt.subplots(figsize=(8, 4))
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_visible(False)
        ax.yaxis.set_visible(False)

        ax.plot(
            x,
            regular_counts["count"],
            marker="o",
            markersize=4,
            color="#3572a5",
            label=labels["daily_regular"],
        )
        ax.plot(
            x,
            sample_counts["count"],
            marker="o",
            markersize=4,
            color="#e67e22",
            label=labels["daily_sample"],
        )
        ax.plot(
            x,
            stub_counts["count"],
            marker="o",
            markersize=4,
            color="#2ca02c",
            label=labels["daily_old_url"],
        )

        ax.set_title(labels["daily_title"])
        ax.set_xticks(x)
        ax.set_xticklabels(dates_display, rotation=45, ha="right")
        ax.legend(frameon=False, loc="upper left")
        ax.set_ylim(bottom=0, top=y_max * 1.15)

        for i, v in enumerate(regular_counts["count"]):
            if v > 0:
                ax.text(
                    i,
                    v + (y_max * 0.05),
                    str(int(v)),
                    ha="center",
                    fontsize=9,
                    color="#3572a5",
                )
        for i, v in enumerate(sample_counts["count"]):
            if v > 0:
                ax.text(
                    i,
                    v + (y_max * 0.12),
                    str(int(v)),
                    ha="center",
                    fontsize=9,
                    color="#e67e22",
                )
        for i, v in enumerate(stub_counts["count"]):
            if v > 0:
                ax.text(
                    i,
                    v + (y_max * 0.19),
                    str(int(v)),
                    ha="center",
                    fontsize=9,
                    color="#2ca02c",
                )

        plt.tight_layout()
        plt.savefig(
            _graph_filename("daily_activity", lang),
            dpi=100,
            bbox_inches="tight",
            facecolor="white",
            edgecolor="none",
        )
        plt.close()
    return True


def create_distributions_graph(df):
    """Популярность распределений — RU и EN (подписи распределений локализованы)."""
    df = df.copy()
    df = df[~df["file_name"].apply(is_sample_file)]
    df = df[~df["file_name"].apply(is_old_url_stub)]

    all_distributions = []
    for dist_str in df["distributions_selected"].dropna():
        distributions = parse_distributions_list(dist_str)
        all_distributions.extend(distributions)

    if not all_distributions:
        return False

    dist_counts = Counter(all_distributions)
    top_dist = pd.Series(dist_counts).sort_values(ascending=True)
    if top_dist.empty:
        return False

    GRAPHS_DIR.mkdir(exist_ok=True)
    for lang in ("ru", "en"):
        labels = ANALYTICS_LABELS[lang]
        y_labels = [_dist_label(str(name), lang) for name in top_dist.index]

        fig, ax = plt.subplots(figsize=(8, 4))
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_visible(False)
        ax.spines["bottom"].set_visible(False)
        ax.xaxis.set_visible(False)

        y_pos = np.arange(len(top_dist))
        bars = ax.barh(y_pos, top_dist.values, color="#3572a5", height=0.6)
        ax.set_title(labels["dist_title"], x=0.35)
        ax.set_yticks(y_pos)
        ax.set_yticklabels(y_labels)
        ax.tick_params(axis="y", length=0)

        for bar, value in zip(bars, top_dist.values):
            width = bar.get_width()
            ax.text(
                width + (max(top_dist.values) * 0.01),
                bar.get_y() + bar.get_height() / 2,
                str(value),
                va="center",
            )

        ax.set_xlim(left=0, right=max(top_dist.values) * 1.1)
        plt.tight_layout()
        plt.savefig(
            _graph_filename("distributions", lang),
            dpi=100,
            bbox_inches="tight",
            facecolor="white",
            edgecolor="none",
        )
        plt.close()
    return True


def _analytics_markdown_block(lang: str, daily_ok, dist_ok, cloud_ok) -> str:
    """Фрагмент README для одного языка."""
    labels = ANALYTICS_LABELS[lang]
    if lang == "ru":
        start, end = "<!-- START_ANALYTICS -->", "<!-- END_ANALYTICS -->"
    else:
        start, end = "<!-- START_ANALYTICS_EN -->", "<!-- END_ANALYTICS_EN -->"

    parts = [start, ""]
    if daily_ok:
        path = _graph_filename("daily_activity", lang).as_posix()
        parts.append(f"![{labels['alt_daily']}]({path})")
        parts.append("")
    if dist_ok:
        path = _graph_filename("distributions", lang).as_posix()
        parts.append(f"![{labels['alt_dist']}]({path})")
        parts.append("")
    if cloud_ok:
        path = _graph_filename("filename_wordcloud", lang).as_posix()
        parts.append(f"![{labels['alt_cloud']}]({path})")
        parts.append("")
    if not daily_ok and not dist_ok and not cloud_ok:
        parts.append(labels["no_data"])
        parts.append("")
    parts.append(end)
    return "\n".join(parts)


def update_readme_with_analytics():
    """Обновляет README.md: графики RU/EN и обе секции аналитики."""
    csv_content = get_analytics_csv()

    if not csv_content:
        return

    lines = csv_content.split("\n")
    if len(lines) < 2:
        return

    df = pd.read_csv(pd.io.common.StringIO(csv_content), sep=CSV_SEPARATOR)

    daily_created = create_daily_activity_graph(df)
    dist_created = create_distributions_graph(df)
    cloud_created = create_filename_wordcloud(df)

    with open("README.md", "r", encoding="utf-8") as f:
        readme_content = f.read()

    for lang in ("ru", "en"):
        block = _analytics_markdown_block(
            lang, daily_created, dist_created, cloud_created
        )
        if lang == "ru":
            pattern = r"<!-- START_ANALYTICS -->[\s\S]*?<!-- END_ANALYTICS -->"
        else:
            pattern = r"<!-- START_ANALYTICS_EN -->[\s\S]*?<!-- END_ANALYTICS_EN -->"

        if re.search(pattern, readme_content):
            readme_content = re.sub(
                pattern, block, readme_content, count=1, flags=re.MULTILINE
            )
        elif lang == "ru":
            readme_content = readme_content.rstrip() + "\n\n" + block + "\n"

    with open("README.md", "w", encoding="utf-8") as f:
        f.write(readme_content)

    commit_changes()

def commit_changes():
    """Коммитит и пушит изменения"""
    try:
        import subprocess
        
        subprocess.run(['git', 'config', '--global', 'user.email', 'actions@github.com'], 
                      check=True, capture_output=True)
        subprocess.run(['git', 'config', '--global', 'user.name', 'GitHub Actions'], 
                      check=True, capture_output=True)
        
        # Добавляем все изменения
        subprocess.run(['git', 'add', 'README.md', 'graphs/'], 
                      check=True, capture_output=True)
        
        # Проверяем есть ли изменения
        result = subprocess.run(['git', 'diff', '--cached', '--quiet'], 
                               capture_output=True)
        if result.returncode != 0:
            commit_msg = f"📊 Обновление аналитики {datetime.now().strftime('%Y-%m-%d')}"
            subprocess.run(['git', 'commit', '-m', commit_msg], 
                          check=True, capture_output=True)
            subprocess.run(['git', 'push'], 
                          check=True, capture_output=True)
    except:
        pass

if __name__ == '__main__':
    update_readme_with_analytics()
