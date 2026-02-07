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
plt.style.use('seaborn-v0_8-darkgrid')

# Конфигурация
GITHUB_REPO_OWNER = "IliaKurdukov"
GITHUB_REPO_NAME = "the_security_curves"
CSV_SEPARATOR = ";"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GRAPHS_DIR = Path("graphs")

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
    """Создает график активности по дням"""
    # Преобразуем столбец date в datetime
    df['datetime'] = pd.to_datetime(df['date'])
    
    # Определяем вчерашнюю дату как datetime
    yesterday = datetime.now() - timedelta(days=1)
    yesterday_date = yesterday.date()
    
    # Создаем полный диапазон дат: от "15 дней назад" до "вчера"
    date_range = pd.date_range(end=yesterday_date, periods=15, freq='D')
    
    # Группируем по дате - используем cutoff_date как datetime для сравнения
    cutoff_date = yesterday - timedelta(days=14)  # 15 дней назад (14 + вчера = 15)
    
    # Преобразуем cutoff_date в тот же тип, что и df['datetime']
    cutoff_date_dt = pd.Timestamp(cutoff_date)
    
    # Фильтруем и группируем
    daily_counts = df[df['datetime'] >= cutoff_date_dt].groupby('date').size().reset_index(name='count')
    daily_counts['date'] = pd.to_datetime(daily_counts['date'])
    
    # Создаем полный DataFrame с всеми датами, заполняя отсутствующие нулями
    full_dates = pd.DataFrame({'date': date_range})
    full_counts = pd.merge(full_dates, daily_counts, on='date', how='left').fillna(0)
    full_counts = full_counts.sort_values('date')
    
    # Форматируем даты для отображения
    dates_display = [d.strftime('%d.%m') for d in full_counts['date']]
    
    fig, ax = plt.subplots(figsize=(8, 4))
    
    # Убираем границы
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    
    # Убираем ось Y (левую вертикальную)
    ax.yaxis.set_visible(False)
    
    # Создаем line plot
    x = np.arange(len(dates_display))
    ax.plot(x, full_counts['count'], 
            marker='o', 
            markersize=4,
            color='#3572a5')
    
    # Настройка внешнего вида - заголовок сдвинут влево
    ax.set_title('Динамика количества использований по дням')
    
    # Устанавливаем подписи на оси X
    ax.set_xticks(x)
    ax.set_xticklabels(dates_display, rotation=45, ha='right')
    
    # Настройка пределов оси Y
    y_max = max(full_counts['count'].max(), 5)
    ax.set_ylim(bottom=0, top=y_max * 1.1) 
    
    # Добавляем значения над точками, пропуская нули
    for i, v in enumerate(full_counts['count']):
        if v > 0:  # Только для ненулевых значений
            ax.text(i, v + (y_max * 0.05), str(int(v)), 
                    ha='center',
                    fontsize=10)
    
    plt.tight_layout()
    
    # Сохраняем график
    GRAPHS_DIR.mkdir(exist_ok=True)
    plt.savefig(GRAPHS_DIR / 'daily_activity.png', 
                dpi=100, 
                bbox_inches='tight',
                facecolor='white',
                edgecolor='none')
    plt.close()
    
    return True

def create_distributions_graph(df):
    """Создает график популярности распределений"""
    all_distributions = []
    for dist_str in df['distributions_selected'].dropna():
        distributions = parse_distributions_list(dist_str)
        all_distributions.extend(distributions)

    if not all_distributions:
        return False

    dist_counts = Counter(all_distributions)
    top_dist = pd.Series(dist_counts).sort_values(ascending=True)

    if top_dist.empty:
        return False

    fig, ax = plt.subplots(figsize=(8, 4))

    # Убираем границы
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.spines['bottom'].set_visible(False)

    # Убираем ось X
    ax.xaxis.set_visible(False)

    # Создаем горизонтальный bar plot
    y_pos = np.arange(len(top_dist))
    bars = ax.barh(y_pos, top_dist.values, 
                   color='#3572a5',
                   height=0.6)

    # Настройка внешнего вида
    ax.set_title('Самые распространенные распределения (кол-во использований)', x=0.35)

    # Устанавливаем подписи на оси Y
    ax.set_yticks(y_pos)
    ax.set_yticklabels(top_dist.index)
    
    # Убираем черточки (ticks) на оси Y
    ax.tick_params(axis='y', length=0)

    # Добавляем значения в концы столбцов
    for i, (bar, value) in enumerate(zip(bars, top_dist.values)):
        width = bar.get_width()
        ax.text(width + (max(top_dist.values) * 0.01), 
                bar.get_y() + bar.get_height()/2,
                str(value),
                va='center')

    # Автонастройка пределов оси X
    ax.set_xlim(left=0, right=max(top_dist.values) * 1.1)

    plt.tight_layout()

    # Сохраняем график
    GRAPHS_DIR.mkdir(exist_ok=True)
    plt.savefig(GRAPHS_DIR / 'distributions.png', 
                dpi=100, 
                bbox_inches='tight',
                facecolor='white',
                edgecolor='none')
    plt.close()
    
    return True

def update_readme_with_analytics():
    """Обновляет README.md с новой аналитикой"""
    csv_content = get_analytics_csv()
    
    if not csv_content:
        return
    
    lines = csv_content.split('\n')
    if len(lines) < 2:
        return
    
    df = pd.read_csv(pd.io.common.StringIO(csv_content), sep=CSV_SEPARATOR)
    
    # Создаем графики
    daily_created = create_daily_activity_graph(df)
    dist_created = create_distributions_graph(df)
    
    # Формируем секцию аналитики
    today = datetime.now().strftime("%d.%m.%Y %H:%M")
    
    analytics_section = f"""<!-- START_ANALYTICS -->

"""
    
    if daily_created:
        analytics_section += """
![Динамика использований](graphs/daily_activity.png)

"""
    
    if dist_created:
        analytics_section += """
![Популярные распределения](graphs/distributions.png)

"""
    
    if not daily_created and not dist_created:
        analytics_section += "*Нет данных для отображения*\n\n"
    
    analytics_section += "<!-- END_ANALYTICS -->"
    
    # Читаем и обновляем README
    with open('README.md', 'r', encoding='utf-8') as f:
        readme_content = f.read()
    
    pattern = r'<!-- START_ANALYTICS -->[\s\S]*?<!-- END_ANALYTICS -->'
    if re.search(pattern, readme_content):
        new_content = re.sub(pattern, analytics_section, readme_content, flags=re.MULTILINE)
    else:
        new_content = readme_content.rstrip() + '\n\n' + analytics_section
    
    with open('README.md', 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    # Коммитим изменения
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
