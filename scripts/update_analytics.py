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
    df['datetime'] = pd.to_datetime(df['date'])
    cutoff_date = datetime.now() - timedelta(days=15)
    df_recent = df[df['datetime'] >= cutoff_date]

    daily_counts = df_recent.groupby('date').size().reset_index(name='count')
    daily_counts = daily_counts.sort_values('date')
    
    if daily_counts.empty:
        return False
    
    # Форматируем даты для отображения
    dates_display = [datetime.strptime(d, '%Y-%m-%d').strftime('%d.%m') 
                     for d in daily_counts['date']]
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Создаем line plot с улучшенным дизайном
    x = np.arange(len(dates_display))
    ax.plot(x, daily_counts['count'], 
            marker='o', 
            linewidth=3, 
            markersize=8,
            color='#3572a5',
            markerfacecolor='white',
            markeredgewidth=2,
            markeredgecolor='#3572a5')
    
    # Настройка внешнего вида
    ax.set_title('📈 Динамика использований', fontsize=16, fontweight='bold', pad=20)
    ax.set_xlabel('Дата', fontsize=12)
    ax.set_ylabel('Количество использований', fontsize=12)
    
    # Устанавливаем подписи на оси X
    ax.set_xticks(x)
    ax.set_xticklabels(dates_display, rotation=45, ha='right')
    
    # Добавляем сетку
    ax.grid(True, alpha=0.3, linestyle='--')
    
    # Настройка пределов оси Y
    y_max = max(daily_counts['count'].max(), 5)
    ax.set_ylim(bottom=0, top=y_max * 1.1)
    
    # Добавляем значения над точками
    for i, v in enumerate(daily_counts['count']):
        ax.text(i, v + (y_max * 0.02), str(v), 
                ha='center', 
                fontweight='bold',
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
    top_dist = pd.Series(dist_counts).sort_values(ascending=False).head(8)
    
    if top_dist.empty:
        return False
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Создаем горизонтальный bar plot
    y_pos = np.arange(len(top_dist))
    bars = ax.barh(y_pos, top_dist.values, 
                   color='#3572a5',
                   edgecolor='white',
                   linewidth=2,
                   height=0.6)
    
    # Настройка внешнего вида
    ax.set_title('📊 Самые распространенные распределения', 
                 fontsize=16, 
                 fontweight='bold', 
                 pad=20)
    ax.set_xlabel('Количество использований', fontsize=12)
    
    # Устанавливаем подписи на оси Y
    ax.set_yticks(y_pos)
    ax.set_yticklabels(top_dist.index)
    
    # Добавляем сетку
    ax.grid(True, alpha=0.3, linestyle='--', axis='x')
    
    # Добавляем значения в концы столбцов
    for i, (bar, value) in enumerate(zip(bars, top_dist.values)):
        width = bar.get_width()
        ax.text(width + (max(top_dist.values) * 0.01), 
                bar.get_y() + bar.get_height()/2,
                str(value),
                va='center',
                fontweight='bold',
                fontsize=10)
    
    # Автонастройка пределов оси X
    ax.set_xlim(left=0, right=max(top_dist.values) * 1.15)
    
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
> 📅 Последнее обновление: {today}

"""
    
    if daily_created:
        analytics_section += """### 📈 Динамика использований
![Динамика использований](graphs/daily_activity.png)

"""
    
    if dist_created:
        analytics_section += """### 📊 Самые распространенные распределения
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
