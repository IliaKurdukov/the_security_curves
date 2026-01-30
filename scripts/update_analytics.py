"""
Скрипт для обновления аналитики в README.md
Запускается через GitHub Actions
"""

import pandas as pd
from datetime import datetime, timedelta
import requests
import base64
import os
from collections import Counter
import re

# Конфигурация
GITHUB_REPO_OWNER = "IliaKurdukov"
GITHUB_REPO_NAME = "the_security_curves"
CSV_SEPARATOR = ";"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

def get_analytics_csv():
    """Загружает CSV с аналитикой из GitHub"""
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/contents/analytics.csv"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print("CSV файл не найден")
            return None
        
        file_data = response.json()
        content = base64.b64decode(file_data['content']).decode('utf-8')
        return content
    except Exception as e:
        print(f"Ошибка загрузки CSV: {e}")
        return None

def parse_distributions_list(dist_str):
    """Парсит строку с распределениями"""
    if not dist_str or dist_str == "[]":
        return []
    
    try:
        # Убираем квадратные скобки и кавычки
        dist_str = dist_str.strip("[]'\"")
        if not dist_str:
            return []
        
        # Разделяем по запятой
        items = [item.strip().strip("'\"") for item in dist_str.split(",")]
        return [item for item in items if item]
    except:
        return []

def generate_daily_activity_mermaid(df):
    """Генерирует mermaid график активности по дням"""
    df['datetime'] = pd.to_datetime(df['date'])
    cutoff_date = datetime.now() - timedelta(days=15)
    df_recent = df[df['datetime'] >= cutoff_date]

    daily_counts = df_recent.groupby('date').size().reset_index(name='count')
    daily_counts = daily_counts.sort_values('date')

    dates_formatted = []
    for date_str in daily_counts['date']:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        dates_formatted.append(f'"{date_obj.strftime("%d.%m")}"')

    # ВАЖНО: Возвращаем ЧИСТЫЙ код диаграммы, без обратных кавычек.
    mermaid_code = f"""xychart-beta
    title "📈 Динамика использований"
    x-axis [{", ".join(dates_formatted)}]
    y-axis "Использований" 0 --> {max(daily_counts['count'].max(), 5)}
    line [{", ".join(map(str, daily_counts['count']))}]
"""
    return mermaid_code

def generate_distributions_mermaid(df):
    """Генерирует mermaid график популярности распределений"""
    all_distributions = []
    for dist_str in df['distributions_selected'].dropna():
        distributions = parse_distributions_list(dist_str)
        all_distributions.extend(distributions)

    if not all_distributions:
        return "graph TD\n    A[\"📊 Распределения не выбраны\"]"

    from collections import Counter
    dist_counts = Counter(all_distributions)
    top_dist = pd.Series(dist_counts).sort_values(ascending=False)

    categories = []
    values = []
    for dist, count in top_dist.head(8).items():
        categories.append(f'"{dist}"')
        values.append(str(count))

    # ВАЖНО: Возвращаем ЧИСТЫЙ код диаграммы, без обратных кавычек.
    mermaid_code = f"""bar
    title "📊 Топ распределений"
    x-axis "{", ".join(categories)}" [{", ".join(values)}]
"""
    return mermaid_code

def update_readme_with_analytics():
    """Обновляет README.md с новой аналитикой"""
    print("Загружаем данные аналитики...")
    csv_content = get_analytics_csv()
    
    if not csv_content:
        print("Нет данных для аналитики")
        return
    
    # Читаем CSV
    lines = csv_content.split('\n')
    if len(lines) < 2:
        print("CSV файл пустой")
        return
    
    # Парсим CSV
    df = pd.read_csv(pd.io.common.StringIO(csv_content), sep=CSV_SEPARATOR)
    
    print(f"Загружено {len(df)} записей")
    
    # Генерируем mermaid графики
    print("Генерируем графики...")
    
    # 1. Активность по дням
    mermaid_daily = generate_daily_activity_mermaid(df)
    
    # 2. Популярность распределений
    mermaid_dist = generate_distributions_mermaid(df)
    
    # Формируем секцию аналитики
    today = datetime.now().strftime("%d.%m.%Y %H:%M")
    
    analytics_section = f"""<!-- START_ANALYTICS -->

```mermaid
%%{{init: {{'theme': 'base', 'config': {{'width': 300, 'height': 200, 'showDataLabel': true}}}}}}%%
{mermaid_daily}
```

```mermaid
{mermaid_dist}
```

<!-- END_ANALYTICS -->"""
    
    # Читаем текущий README
    print("Обновляем README.md...")
    with open('README.md', 'r', encoding='utf-8') as f:
        readme_content = f.read()
    
    # Заменяем секцию аналитики
    pattern = r'<!-- START_ANALYTICS -->[\s\S]*?<!-- END_ANALYTICS -->'
    if re.search(pattern, readme_content):
        new_content = re.sub(pattern, analytics_section, readme_content, flags=re.MULTILINE)
    else:
        # Если секции нет, добавляем в конец
        new_content = readme_content.rstrip() + '\n\n' + analytics_section
    
    # Сохраняем обновленный README
    with open('README.md', 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print("README.md успешно обновлен!")
    
    # Коммитим изменения
    commit_changes()

def commit_changes():
    try:
        import subprocess
        subprocess.run(['git', 'config', '--global', 'user.email', 'actions@github.com'], check=True)
        subprocess.run(['git', 'config', '--global', 'user.name', 'GitHub Actions'], check=True)
        
        subprocess.run(['git', 'add', 'README.md'], check=True)
        
        # Проверяем есть ли изменения
        result = subprocess.run(['git', 'diff', '--cached', '--quiet'], capture_output=True)
        if result.returncode != 0:
            commit_msg = f"📊 Обновление аналитики {datetime.now().strftime('%Y-%m-%d')}"
            subprocess.run(['git', 'commit', '-m', commit_msg], check=True)
            subprocess.run(['git', 'push'], check=True)
            print("Изменения закоммичены и запушены")
        else:
            print("Нет изменений для коммита")
    except Exception as e:
        print(f"Ошибка при коммите: {e}")

if __name__ == '__main__':
    update_readme_with_analytics()
