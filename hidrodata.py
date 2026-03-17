import base64
import hashlib
import json
import lmoments3 as lm
import math
import matplotlib.pyplot as plt
import numpy as np
import os
import pandas as pd
import re
import requests
import scipy.stats as stats
import streamlit as st
import streamlit.components.v1 as components
import subprocess
import sys
import uuid
import xlrd
from abc import ABC, abstractmethod
from datetime import date, datetime
from lmoments3 import distr
from math import pi
from scipy.integrate import quad
from scipy.optimize import minimize, brentq
from sklearn.metrics import mean_absolute_error, r2_score, max_error
from sympy import EulerGamma

# Простая функция Anderson-Darling теста для сравнения распределений
def anderson_darling_test(data, cdf_func):
    """
    Anderson-Darling тест для сравнения распределений
    data: эмпирические данные
    cdf_func: функция распределения F(x)
    возвращает: A-D статистику (чем меньше, тем лучше)
    """
    n = len(data)
    sorted_data = np.sort(data)
    
    # Оптимизация: векторизуем вычисление CDF значений
    cdf_values = np.vectorize(cdf_func)(sorted_data)
    
    # Избегаем log(0) и log(1)
    cdf_values = np.clip(cdf_values, 1e-12, 1 - 1e-12)
    
    # Статистика Anderson-Darling
    i = np.arange(1, n + 1)
    term = (2 * i - 1) * (np.log(cdf_values) + np.log(1 - cdf_values[::-1]))
    A2 = -n - (1/n) * np.sum(term)
    
    return A2

ru_dict = {'page_title': "Кривые обеспеченности",
           'title': "📉 Кривые обеспеченности"}

# ==================== СИСТЕМА АНАЛИТИКИ ====================
GITHUB_REPO_OWNER = "IliaKurdukov"
GITHUB_REPO_NAME = "the_security_curves"
GITHUB_BRANCH = "main"
CSV_SEPARATOR = ";"  # Новый разделитель вместо запятой

# Список тестовых файлов, которые не должны логироваться
TEST_FILES = ["тест.xlsx"]

def get_session_id():
    if 'session_id' not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    return st.session_state.session_id

def get_github_token():
    try:
        return st.secrets.get("github_token", None)
    except:
        return None

def get_csv_from_github(token):
    """Получает CSV файл с GitHub"""
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/contents/analytics.csv"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return None, None, []
        
        file_data = response.json()
        content = base64.b64decode(file_data['content']).decode('utf-8')
        sha = file_data['sha']
        return sha, content
    except:
        return None, None

def save_to_github(token, sha, content):
    """Сохраняет CSV файл на GitHub"""
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/contents/analytics.csv"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        data = {
            "message": f"Update analytics: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "content": base64.b64encode(content.encode('utf-8')).decode('utf-8'),
            "sha": sha,
            "branch": GITHUB_BRANCH
        }
        
        response = requests.put(url, headers=headers, json=data)
        return response.status_code in [200, 201]
    except:
        return False

def is_test_file(filename):
    """Проверяет, является ли файл тестовым"""
    if not filename:
        return False
    return any(test_file.lower() in filename.lower() for test_file in TEST_FILES)

def format_list_for_csv(items):
    """Форматирует список в строку для CSV"""
    if not items:
        return "[]"
    # Экранируем кавычки и разделители
    return "[" + ", ".join(str(item).replace('"', '""') for item in items) + "]"

def parse_list_from_csv(csv_string):
    """Парсит список из CSV строки"""
    if not csv_string or csv_string == "[]":
        return []
    try:
        # Убираем квадратные скобки
        items = csv_string[1:-1].split(", ")
        return [item.strip().replace('""', '"') for item in items if item.strip()]
    except:
        return []

def log_analytics(uploaded_file=None, distributions_selected=None, custom_ensurence_value=None):
    """Создает/обновляет запись в аналитике - только последний выбор"""
    try:
        token = get_github_token()
        if not token or not uploaded_file:
            return False
        
        # ПРОВЕРКА: если файл тестовый - НЕ логируем
        if is_test_file(uploaded_file.name):
            return False
        
        session_id = get_session_id()
        
        # Получаем текущий CSV
        sha, content = get_csv_from_github(token)
        if sha is None:
            return False
        
        # Разбираем CSV
        lines = content.split('\n')
        if not lines or len(lines) < 2:
            # Создаем новый файл с заголовком
            headers = f"date{CSV_SEPARATOR}time{CSV_SEPARATOR}session_id{CSV_SEPARATOR}file_name{CSV_SEPARATOR}file_size{CSV_SEPARATOR}file_rows{CSV_SEPARATOR}distributions_selected{CSV_SEPARATOR}distributions_count{CSV_SEPARATOR}custom_ensurence_value"
            lines = [headers, ""]
        
        # Ищем запись этой сессии
        session_found = False
        for i in range(1, len(lines)):
            if lines[i].strip() and session_id in lines[i]:
                session_found = True
                session_line_index = i
                break
        
        now = datetime.now()
        date_str = date.today().isoformat()
        time_str = now.strftime('%H:%M:%S')
        
        if session_found:
            # ОБНОВЛЯЕМ существующую запись - берем только последние значения!
            parts = lines[session_line_index].split(CSV_SEPARATOR)
            
            # Обновляем ВСЕ поля на текущие значения (перезаписываем полностью)
            parts[0] = date_str  # date
            parts[1] = time_str  # time
            
            # distributions_selected - берем только текущий выбор
            if distributions_selected is not None:
                parts[6] = format_list_for_csv(list(distributions_selected))
                parts[7] = str(len(distributions_selected))
            
            # custom_ensurence_value - добавляем только если не 0.001
            if custom_ensurence_value is not None:
                # Получаем текущий список значений
                current_values = parse_list_from_csv(parts[8]) if len(parts) > 8 else []
                custom_float = float(custom_ensurence_value)
                
                # Добавляем только если не значение по умолчанию
                if abs(custom_float - 0.001) > 0.0001:
                    # Конвертируем все в float для сравнения
                    current_floats = []
                    for v in current_values:
                        try:
                            current_floats.append(float(v))
                        except:
                            pass
                    
                    # Добавляем если еще нет
                    if custom_float not in current_floats:
                        current_values.append(str(custom_float))
                
                parts[8] = format_list_for_csv(current_values)
            
            lines[session_line_index] = CSV_SEPARATOR.join(parts)
            
        else:
            # СОЗДАЕМ новую запись
            # distributions_selected - текущий выбор
            dist_list = list(distributions_selected) if distributions_selected else []
            
            # custom_ensurence_value - только если не 0.001
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
                "None",  # file_rows будет обновлено позже
                format_list_for_csv(dist_list),
                str(len(dist_list)),
                format_list_for_csv(custom_values)
            ]
            
            new_line = CSV_SEPARATOR.join(new_line_parts)
            
            # Добавляем в конец
            if lines[-1] == "":
                lines[-1] = new_line
            else:
                lines.append(new_line)
            lines.append("")  # Пустая строка в конце
        
        # Сохраняем обратно
        new_content = '\n'.join(lines)
        return save_to_github(token, sha, new_content)
        
    except Exception as e:
        return False

def update_analytics_file_rows(file_rows):
    """Обновляет количество строк в файле"""
    try:
        token = get_github_token()
        if not token:
            return False
        
        session_id = get_session_id()
        
        # Получаем текущий CSV
        sha, content = get_csv_from_github(token)
        if sha is None:
            return False
        
        # Разбираем и обновляем
        lines = content.split('\n')
        for i in range(1, len(lines)):
            if lines[i].strip() and session_id in lines[i]:
                parts = lines[i].split(CSV_SEPARATOR)
                if len(parts) > 5:
                    # Проверяем, не тестовый ли это файл
                    if len(parts) > 3 and is_test_file(parts[3]):
                        # Если это тестовый файл, просто удаляем запись
                        lines.pop(i)
                    else:
                        # Иначе обновляем количество строк
                        parts[5] = str(file_rows)
                        lines[i] = CSV_SEPARATOR.join(parts)
                    break
        
        # Сохраняем обратно
        new_content = '\n'.join(lines)
        return save_to_github(token, sha, new_content)
        
    except Exception as e:
        return False

# ==================== КОНЕЦ СИСТЕМЫ АНАЛИТИКИ ====================

st.set_page_config(
    page_title=ru_dict['page_title'],
    page_icon="📉",
    layout="wide",
    menu_items={
        'About': "Приложение для анализа экстремальных событий"
    }
)

st.title(ru_dict['title'])

st.sidebar.markdown("""
### ℹ️ О проекте
Приложение автоматически строит кривые обеспеченности по сырым данным.

Пишите ваши вопросы и предложения, узнавайте актуальные новости и информацию о других проектов в области гидрометеорологии в [нашем канале](https://t.me/+g8Kjj2t8hvsxYmJi).

Также осуществляем расчет климатических параметров по вашим данным или по имеющейся базе данных из 600+ метеостанций:
- Температура воздуха и почвы
- Атмосферные осадки
- Влажность воздуха
- Снежный покров
- Атмосферные явления
- Характеристики ветра
- Опасные метеорологические явления
- Снегоперенос
- Испарение с водной поверхности

Подробнее: [Камышев Арсений](https://t.me/Arseniikamyshev), [Курдюков Илья](https://t.me/ilia_kurdukov)


Наш проект некоммерческий, и мы будем благодарны [вашей поддержке](https://tbank.ru/cf/2PlIaU81b0F) на его развитие 🍩

🙏 Спасибо за поддержку: Мише Самохину, Никите З., Татьяне Д., Елене Л., Марине М., Валентину Марченко, Татьяне Ш., Алмазу Х., Сергею, Ивану К., Евгению К., Константину Д., Дмитрию К.
""")

# Функция для чтения Excel с автоматической установкой зависимостей
def smart_read_excel(uploaded_file):
    file_extension = uploaded_file.name.split('.')[-1].lower()
    
    if file_extension == 'xls':
        try:
            return pd.read_excel(uploaded_file, engine='xlrd')
        except ImportError:
            # Устанавливаем xlrd если нужно
            subprocess.check_call([sys.executable, "-m", "pip", "install", "xlrd>=2.0.1"])
            return pd.read_excel(uploaded_file, engine='xlrd')
    
    elif file_extension == 'xlsx':
        try:
            return pd.read_excel(uploaded_file, engine='openpyxl')
        except ImportError:
            # Устанавливаем openpyxl если нужно
            subprocess.check_call([sys.executable, "-m", "pip", "install", "openpyxl"])
            return pd.read_excel(uploaded_file, engine='openpyxl')

# Функции для распределения Крицкого-Менкеля
def km_pdf(k, γ, a, b):
    return γ**γ / (a**(γ/b) * math.gamma(γ) * b) * math.exp(-γ*(k/a)**(1/b)) * k**(γ/b-1)

def km_log_pdf(k, γ, a, b):
    return γ * math.log(γ) - (γ/b)*math.log(a) - math.log(math.gamma(γ)) - math.log(b) - γ*(k/a)**(1/b) + (γ/b-1)*math.log(k)

def km_cdf(k, γ, a, b):
    integral, error = quad(km_pdf, 1e-10, k, args=(γ, a, b))
    return integral

def log_likelihood(params, data):
    """Логарифмическое правдоподобие"""
    γ, a, b = params
    if γ <= 1e-10 or a <= 1e-10 or b <= 1e-10:
        return -1e10
    total = 0.0
    for z in data:
        if z <= 0:
            continue
        log_pdf = km_log_pdf(z, γ, a, b)
        total += log_pdf
    return total

def km_fit(data, initial_params = [2, 1, 1]):
    data = data / data.mean()
    result = minimize(
        lambda params: -log_likelihood(params, data),
        initial_params,
        method='L-BFGS-B',
        bounds=[(1e-10, None), (1e-10, None), (1e-10, None)],
        options={'maxiter': 10000, 'ftol': 1e-12}
    )
    return result.x

# Функции для расчета моментов распределения Крицкого-Менкеля
def km_mean(γ, a, b):
    """Математическое ожидание распределения Крицкого-Менкеля"""
    def integrand(k):
        return k * km_pdf(k, γ, a, b)
    
    result, error = quad(integrand, 1e-10, a * 100)  # Ограничиваем верхнюю границу
    return result

def km_variance(γ, a, b):
    """Дисперсия распределения Крицкого-Менкеля"""
    def second_moment_integrand(k):
        return k**2 * km_pdf(k, γ, a, b)
    
    E_X2, _ = quad(second_moment_integrand, 1e-10, a * 100)
    E_X = km_mean(γ, a, b)
    return E_X2 - E_X**2

def km_std(γ, a, b):
    """Среднеквадратическое отклонение"""
    return math.sqrt(km_variance(γ, a, b))

def km_coefficient_of_variation(γ, a, b):
    """Коэффициент вариации"""
    μ = km_mean(γ, a, b)
    σ = km_std(γ, a, b)
    return σ / μ

def km_coefficient_of_skewness(γ, a, b):
    """Коэффициент асимметрии"""
    μ = km_mean(γ, a, b)
    σ = km_std(γ, a, b)
    
    def third_central_moment_integrand(k):
        return (k - μ)**3 * km_pdf(k, γ, a, b)
    
    E_X_minus_μ_cubed, _ = quad(third_central_moment_integrand, 1e-10, a * 100)
    return E_X_minus_μ_cubed / (σ**3)

uploaded_file = st.file_uploader("Загрузите Excel файл", type=['xls', 'xlsx'])
if uploaded_file:
    try:
        df = smart_read_excel(uploaded_file)
        def pluralize_rows(number: int) -> str:
            if number % 10 == 1 and number % 100 != 11:
                return "строку"  # 1 строка (но 11, 111, 211 и т.д. — "строк")
            elif 2 <= number % 10 <= 4 and (number % 100 < 10 or number % 100 >= 20):
                return "строки"  # 2, 3, 4 строки (но 12, 13, 14 — "строк")
            else:
                return "строк"  # 0, 5-20, 25-30 и т.д.
        st.success(f"Данные успешно загружены и содержат {len(df)} {pluralize_rows(len(df))}")
        # Логируем загрузку файла
        log_analytics(uploaded_file=uploaded_file)
        # Обновляем количество строк после обработки
        update_analytics_file_rows(len(df))
        with st.expander("🔢 Фрагмент загруженных данных", expanded=False):
            st.markdown(df.head().to_html(), unsafe_allow_html=True)

        # Автоматическое определение столбцов
        numeric_cols = df.select_dtypes(include=['number']).columns
        cols = df.columns.tolist()
        if len(numeric_cols) == 0:
            st.error("В файле нет числовых столбцов")
            st.stop()
        else:
            values_col = st.selectbox("Выберите столбец с данными для построения кривой обеспеченности", numeric_cols)
            df.rename(columns={values_col: str(values_col)}, inplace=True)
            cols.insert(0, 'Без группировки')
            index_col = st.selectbox("Выберите столбец для группировки данных", cols)
            if index_col != 'Без группировки':
                aggfunc = st.selectbox("Выберите способ группировки данных", ['Максимальные значения', 'Средние значения', 'Минимальные значения'])
                df.rename(columns={index_col: str(index_col)}, inplace=True)
            
            with st.expander("🔢 Хронологический ряд значений и эмпирическое распределение", expanded=False):
                if index_col != 'Без группировки':
                    aggfunc_dict = {'Максимальные значения': 'max', 'Средние значения': 'mean', 'Минимальные значения': 'min'}
                    data = df.pivot_table(index = index_col, values = values_col, aggfunc = aggfunc_dict[aggfunc])
                else:
                    data = df[values_col]
                data = pd.DataFrame(data)
                scaler = data.mean()
                n = len(data)
                data['Ранг'] = np.arange(1, n + 1)
                max_rank_plus_one = n + 1
                data['Вероятность'] = data['Ранг'] / max_rank_plus_one
                data['Обеспеченность P, %'] = round(data['Вероятность'] * 100, 2)
                if index_col != 'Без группировки':
                    data[index_col] = data.index
                data_to_merge = data.sort_values(by=values_col, ascending = False)
                data_to_merge.drop(['Вероятность', 'Обеспеченность P, %', 'Ранг'], axis=1, inplace=True)
                data_to_merge.rename(columns={values_col: values_col + ' (P)'}, inplace=True)
                if index_col != 'Без группировки':
                    data_to_merge.rename(columns={index_col: index_col + ' (P)'}, inplace=True)
                    data_to_merge[index_col + ' (P)'] = data_to_merge.index
                # Оптимизация: создаем ранг сразу с правильными значениями
                data_to_merge['Ранг'] = np.arange(1, n + 1)
                data = data.merge(data_to_merge, on = 'Ранг')
                data.set_index('Ранг', inplace=True)
                if index_col != 'Без группировки':
                    st.markdown(data[[index_col, values_col, 'Обеспеченность P, %', values_col + ' (P)', index_col + ' (P)']].to_html(), unsafe_allow_html=True)
                else:
                    st.markdown(data[[values_col, 'Обеспеченность P, %', values_col + ' (P)']].to_html(), unsafe_allow_html=True)
                
            with st.expander("📊 График хода значений", expanded=False):
                 fig, ax = plt.subplots(figsize=(4, 2))
                 x = data[index_col] if index_col != 'Без группировки' else data.index
                 y = data[values_col]
                 plt.plot(x, y, linewidth=0.5)
                 ax.set_ylabel(values_col, fontsize=5)       
                 ax.set_title(f"График хода значений", fontsize=6)
                 ax.tick_params(axis='x', labelsize=5)
                 ax.tick_params(axis='y', labelsize=5)
                 st.pyplot(fig, width='content')

            data = data.sort_values(by=values_col)

            # Базовый интерфейс для всех распределений
            class DistributionAdapter(ABC):
                @abstractmethod
                def fit(self, data):
                    """Возвращает параметры распределения"""
                    pass
                @abstractmethod
                def ppf(self, x, *params):
                    """Квантильная функция"""
                    pass
                @property
                @abstractmethod
                def name(self):
                    """Название распределения для отображения"""
                    pass
           
            # Адаптер для Scipy распределений
            class ScipyDistributionAdapter(DistributionAdapter):
                def __init__(self, scipy_name, display_name):
                    self._dist = getattr(stats, scipy_name)
                    self._display_name = display_name
                def fit(self, data):
                    return self._dist.fit(data)
                def ppf(self, x, *params):
                    return self._dist.ppf(x, *params) 
                @property
                def name(self):
                    return self._display_name
           
            # Адаптер для L-moments распределений
            class LMomentsDistributionAdapter(DistributionAdapter):
                def __init__(self, lmoments_name, display_name):
                    self._lmoments_name = lmoments_name
                    self._display_name = display_name
                def fit(self, data):
                    dist_func = getattr(distr, self._lmoments_name)
                    return list(dist_func.lmom_fit(data).values())
                def ppf(self, x, *params):
                    dist_func = getattr(distr, self._lmoments_name)
                    return dist_func.ppf(x, *params)
                @property
                def name(self):
                    return self._display_name
           
            # Адаптер для кастомных распределений
            class CustomDistributionAdapter(DistributionAdapter):
                def __init__(self, fit_func, ppf_func, display_name):
                    self._fit_func = fit_func
                    self._ppf_func = ppf_func
                    self._display_name = display_name
                def fit(self, data):
                    return self._fit_func(data)
                def ppf(self, x, *params):
                    return self._ppf_func(x, *params)
                @property
                def name(self):
                    return self._display_name
           
            # Фабрика для удобного создания распределений
            class DistributionFactory:
                @staticmethod
                def scipy(scipy_name, display_name):
                    return ScipyDistributionAdapter(scipy_name, display_name)
                @staticmethod
                def lmoments(lmoments_name, display_name):
                    return LMomentsDistributionAdapter(lmoments_name, display_name)
                @staticmethod
                def custom(fit_func, ppf_func, display_name):
                    return CustomDistributionAdapter(fit_func, ppf_func, display_name)

            # Сохраняем scaler для использования в km_ppf
            scaler_value = scaler.iloc[0] if hasattr(scaler, 'iloc') else float(scaler)
            
            # Функция PPF для Крицкого-Менкеля (нужна для адаптера)
            def km_ppf(x, γ, a, b):
                """Квантильная функция распределения Крицкого-Менкеля"""
                def equation(k):
                    return km_cdf(k, γ, a, b) - x
                # Ищем корень на разумном интервале
                sol = brentq(equation, 1e-10, a * 100)
                return sol * scaler_value  # Возвращаем в исходный масштаб
            
            # Функции для распределения Гумбеля методом моментов
            def gumbel_moments_fit(data):
                """Расчет параметров распределения Гумбеля методом моментов"""
                mean = np.mean(data)
                std = np.std(data, ddof=0)  # СКО выборки
                scale = std * (6**(1/2)) / pi
                loc = mean - float(EulerGamma) * scale
                return [loc, scale]
            
            def gumbel_moments_ppf(x, loc, scale):
                """Квантильная функция распределения Гумбеля (использует scipy)"""
                return stats.gumbel_r.ppf(x, loc=loc, scale=scale)
            
            distributions = {
                'Гумбеля (ММП)': DistributionFactory.scipy('gumbel_r', 'Гумбеля (ММП)'),
                'Пирсона 3 типа (ММП)': DistributionFactory.scipy('pearson3', 'Пирсона 3 типа (ММП)'),
                'Обобщенное (ММП)': DistributionFactory.scipy('genextreme', 'Обобщенное (ММП)'),
                'Крицкого-Менкеля (ММП)': DistributionFactory.custom(km_fit, km_ppf, 'Крицкого-Менкеля (ММП)'),
                'Гумбеля (Мом)': DistributionFactory.custom(gumbel_moments_fit, gumbel_moments_ppf, 'Гумбеля (Мом)'),
                'Гумбеля (L-мом)': DistributionFactory.lmoments('gum', 'Гумбеля (L-мом)'),
                'Пирсона 3 типа (L-мом)': DistributionFactory.lmoments('pe3', 'Пирсона 3 типа (L-мом)'),
                'Обобщенное (L-мом)': DistributionFactory.lmoments('gev', 'Обобщенное (L-мом)')
            }

            # Добавляем подсказку с расшифровкой аббревиатур
            st.markdown("""
            <style>
            .dist-tooltip {
                position: relative;
                display: inline-block;
                cursor: help;
                margin-left: 5px;
            }
            .dist-tooltip .dist-tooltiptext {
                visibility: hidden;
                width: 220px;
                background-color: #333;
                color: #fff;
                text-align: left;
                border-radius: 6px;
                padding: 10px;
                position: absolute;
                z-index: 1000;
                bottom: 125%;
                left: 50%;
                margin-left: -110px;
                opacity: 0;
                transition: opacity 0.3s;
                font-size: 12px;
                line-height: 1.5;
                box-shadow: 0 2px 8px rgba(0,0,0,0.3);
            }
            .dist-tooltip .dist-tooltiptext::after {
                content: "";
                position: absolute;
                top: 100%;
                left: 50%;
                margin-left: -5px;
                border-width: 5px;
                border-style: solid;
                border-color: #333 transparent transparent transparent;
            }
            .dist-tooltip:hover .dist-tooltiptext {
                visibility: visible;
                opacity: 1;
            }
            </style>
            <div style="display: flex; align-items: center;">
                <span>Выберите распределение для аппроксимации</span>
                <div class="dist-tooltip">
                    <span style="font-size: 16px; color: #666;">ⓘ</span>
                    <span class="dist-tooltiptext">
                        <b>Расшифровка аббревиатур:</b><br>
                        • <b>ММП</b> - метод максимального правдоподобия<br>
                        • <b>Мом</b> - метод моментов<br>
                        • <b>L-мом</b> - метод L-моментов
                    </span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            distributions_to_plot = st.multiselect(
                '',
                distributions,
                default = [list(distributions)[-1]],
                label_visibility="collapsed"
            )
            # Логируем выбор распределений
            if distributions_to_plot:
                log_analytics(uploaded_file=uploaded_file, 
                         distributions_selected=distributions_to_plot)

            # инициализация функции для изменения масштаба по горизонтальной оси
            def scalefunc(x):
                return stats.norm.ppf(x/100, loc=0, scale=1)

            # График, таблица
            fig, ax = plt.subplots(figsize=(4, 2))

            x = data['Вероятность'] * 100
            y = data[values_col + ' (P)']
            plt.scatter(x, y,
                        label='Эмпирическое',
                        s=5,           # размер точек
                        facecolors='none', # без заливки
                        edgecolors='black', # черный контур
                        linewidths=0.5)    # толщина контура

            # таблица значений с разной обеспеченностью
            percent_list_1 = [0.01, 0.1, 0.33, 0.5, 1, 2, 3, 5, 10, 50, 63, 90, 95, 98, 99, 99.9]
            df_1 = pd.DataFrame(percent_list_1, columns=['Обеспеченность'])

            # таблица характеристик
            parameters = ['Среднее', 'Cv', 'Cs', 'R²', 'MAE', 'maxE', 'A-D']
            parameters_df = pd.DataFrame(parameters, columns=['Распределение'])
            mean = data[values_col].mean()
            std = data[values_col].std()
            cv = (std/mean)
            cs = (stats.skew(data[values_col]))
            parameters_df['Эмпирическое'] = pd.DataFrame([mean, cv, cs, '-', '-', '-', '-'])

            # Функция для округления метрик
            def custom_round(x):
                abs_x = abs(x)
                if abs_x >= 100:  # Если 3+ знака до запятой → округляем до целого
                    return round(x)
                else:  # Иначе оставляем 3 значащих цифры
                    return np.format_float_positional(x, precision=3, fractional=False, trim='-')
            
            # Расчет точности для округления остальных чисел в таблице:
            sample = df.loc[0, values_col]
            if isinstance(sample, (int, np.integer)) or (isinstance(sample, float) and sample.is_integer()):
                precision = 1
            else:
                # Более эффективный способ определения точности
                sample_str = str(sample)
                if '.' in sample_str:
                    precision = len(sample_str.split('.')[1])
                else:
                    precision = 1

            # Вспомогательная функция для создания scipy распределения из L-moments параметров
            def create_scipy_dist_from_lmoments(lmoments_name, params):
                """Создает scipy распределение из параметров L-moments"""
                if lmoments_name == 'gum':
                    return stats.gumbel_r(loc=params[0], scale=params[1])
                elif lmoments_name == 'pe3':
                    return stats.pearson3(skew=params[0], loc=params[1], scale=params[2])
                elif lmoments_name == 'gev':
                    return stats.genextreme(c=params[0], loc=params[1], scale=params[2])
                else:
                    raise ValueError(f"Неизвестное L-moments распределение: {lmoments_name}")
            
            # Вспомогательная функция для форматирования статистики
            def format_stat(value):
                """Форматирует статистику: заменяет nan/inf на 'Не существует'."""
                if np.isnan(value) or np.isinf(value):
                    return "Не существует"
                else:
                    return value
            
            # Словари для хранения параметров и распределений (избегаем повторных вычислений)
            distribution_params = {}
            distribution_objects = {}  # Для хранения scipy распределений
            
            # Оптимизация: создаем x_teor один раз для всех распределений
            range1 = np.arange(0.1, 1.1, 0.2)
            range2 = np.arange(1.1, 2.0, 0.3)      
            range3 = np.arange(2.0, 98.0, 1.0)     
            range4 = np.arange(98.0, 98.9, 0.3)   
            range5 = np.arange(98.9, 99.9, 0.2)   
            # Добавляем 99.9 явно, чтобы график доходил до конца
            x_teor = np.concatenate([range1, range2, range3, range4, range5, [99.9]])
            
            # построение кривой с распределением
            for distribution in distributions_to_plot:
                selected_dist = distributions[distribution]
                # Вычисляем параметры один раз и сохраняем
                params = selected_dist.fit(data[values_col])
                distribution_params[distribution] = params
                
                predict = data['Вероятность'].apply(lambda x: selected_dist.ppf(1-x, *params))
                r2 = r2_score(data[values_col + ' (P)'], predict)
                mae = mean_absolute_error(data[values_col + ' (P)'], predict)
                maxE = max_error(data[values_col + ' (P)'], predict)
                
                # Расчет A-D статистики и сохранение распределения для дальнейшего использования
                try:
                    # Создаем CDF функцию для подобранного распределения
                    if isinstance(selected_dist, ScipyDistributionAdapter):
                        fitted_dist = selected_dist._dist(*params)
                        distribution_objects[distribution] = fitted_dist
                        cdf_func = fitted_dist.cdf
                    elif isinstance(selected_dist, LMomentsDistributionAdapter):
                        # Для L-moments создаем соответствующее scipy распределение
                        fitted_dist = create_scipy_dist_from_lmoments(selected_dist._lmoments_name, params)
                        distribution_objects[distribution] = fitted_dist
                        cdf_func = fitted_dist.cdf
                    elif isinstance(selected_dist, CustomDistributionAdapter) and 'Гумбеля (Мом)' in distribution:
                        # Для Гумбеля (Мом) создаем scipy распределение для A-D теста
                        fitted_dist = stats.gumbel_r(loc=params[0], scale=params[1])
                        distribution_objects[distribution] = fitted_dist
                        cdf_func = fitted_dist.cdf
                    elif isinstance(selected_dist, CustomDistributionAdapter):
                        # Для кастомных распределений создаем обертку для CDF
                        def cdf_func(x):
                            # Для кастомных распределений нам нужно вычислить CDF вручную
                            if 'Крицкого-Менкеля' in distribution:
                                # Для Крицкого-Менкеля используем нашу функцию km_cdf
                                return km_cdf(x / scaler_value, *params)  # Нормализуем данные
                            else:
                                # Для других кастомных распределений можно добавить аналогично
                                return np.nan
                    
                    ad_stat = anderson_darling_test(data[values_col].values, cdf_func)
                    
                except Exception as e:
                    st.warning(f"Не удалось рассчитать A-D статистику для {distribution}: {str(e)}")
                    ad_stat = np.nan

                # Оптимизация: создаем векторизованную функцию
                def f(x):
                    return selected_dist.ppf(1-x/100, *params)
                f2 = np.vectorize(f)
                teor_label = distribution
                plt.plot(x_teor, f2(x_teor), label=teor_label, linewidth=0.7)

                # сбор данных в таблицу c обеспеченностями
                df_1[f'{teor_label}'] = df_1['Обеспеченность'].apply(lambda x: round(selected_dist.ppf(1-x/100, *params), precision))

                # сбор данных в таблицу с параметрами распределения
                # Для scipy распределений
                if isinstance(selected_dist, ScipyDistributionAdapter):
                    # Используем сохраненное распределение, если оно есть, иначе создаем новое
                    if distribution in distribution_objects:
                        dist = distribution_objects[distribution]
                    else:
                        dist = selected_dist._dist(*params)
                    mean = dist.mean()
                    std = dist.std()
                    cv = format_stat(std/mean)
                    cs = format_stat(dist.stats(moments='s'))
                # Для L-moments распределений
                elif isinstance(selected_dist, LMomentsDistributionAdapter):
                    try:
                        # Используем уже созданное распределение из A-D теста
                        if distribution in distribution_objects:
                            dist = distribution_objects[distribution]
                        else:
                            dist = create_scipy_dist_from_lmoments(selected_dist._lmoments_name, params)
                        
                        mean = dist.mean()
                        std = dist.std()
                        cv = format_stat(std/mean)
                        cs = format_stat(dist.stats(moments='s'))
                    except Exception as e:
                        st.warning(f"Ошибка при расчете статистик для {distribution}: {str(e)}")
                        mean = "Ошибка"
                        cv = "Ошибка"
                        cs = "Ошибка"
                # Для кастомного распределения Крицкого-Менкеля
                elif isinstance(selected_dist, CustomDistributionAdapter) and 'Крицкого-Менкеля' in distribution:
                    try:
                        γ, a, b = params
                        mean = km_mean(γ, a, b) * scaler_value  # Возвращаем в исходный масштаб
                        cv = format_stat(km_coefficient_of_variation(γ, a, b))
                        cs = format_stat(km_coefficient_of_skewness(γ, a, b))
                    except Exception as e:
                        st.warning(f"Ошибка при расчете статистик для {distribution}: {str(e)}")
                        mean = "Ошибка"
                        cv = "Ошибка"
                        cs = "Ошибка"
                # Для кастомного распределения Гумбеля (Мом)
                elif isinstance(selected_dist, CustomDistributionAdapter) and 'Гумбеля (Мом)' in distribution:
                    try:
                        # Используем scipy.stats.gumbel_r для расчета статистик
                        dist = stats.gumbel_r(loc=params[0], scale=params[1])
                        mean = dist.mean()
                        std = dist.std()
                        cv = format_stat(std/mean)
                        cs = format_stat(dist.stats(moments='s'))
                    except Exception as e:
                        st.warning(f"Ошибка при расчете статистик для {distribution}: {str(e)}")
                        mean = "Ошибка"
                        cv = "Ошибка"
                        cs = "Ошибка"
                
                parameters_df[f'{teor_label}'] = pd.DataFrame([mean, cv, cs, r2, mae, maxE, ad_stat])

            # добавление линий сетки, масштаба по горизонтальной оси, подписей осей и графика,
            # границ, шага и подписей делений для горизонтальной оси
            ax.xaxis.grid(True)
            plt.xscale('function', functions=[scalefunc, lambda x: x])
            ax.set_xlabel("Обеспеченность, %", fontsize=5)
            ax.set_ylabel(values_col, fontsize=5)       
            ax.set_title(f"Значения с разной долей обеспеченности", fontsize=6)
            ax.set(xlim=(0.1,99.9))
            plt.xticks([0.1, 1, 2, 5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 98, 99, 99.9])
            ax.set_xticklabels([0.1, 1, 2, 5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 98, 99, 99.9])
            plt.legend(title='Вид распределения')
            ax.tick_params(axis='x', labelsize=5)
            ax.tick_params(axis='y', labelsize=5)
            legend = ax.legend(fontsize=5)
            st.pyplot(fig, width='content')

            with st.expander("📋 Расчет значений с разной долей обеспеченности (в %)", expanded=False):
                df_1 = df_1.T
                st.markdown(df_1.to_html(index=True, header=False), unsafe_allow_html=True)

                # ввод значений
                p = st.number_input(
                "Выберите обеспеченность для расчета значения (0 < P < 100)",
                min_value=0.001,
                max_value=99.999,
                format="%.3f"
                )
                # Логируем ввод значения обеспеченности (только если значение изменилось)
                if 'last_logged_p' not in st.session_state or st.session_state.last_logged_p != p:
                    log_analytics(uploaded_file=uploaded_file,
                             distributions_selected=distributions_to_plot,
                             custom_ensurence_value=p)
                    st.session_state.last_logged_p = p
                
                custom_dict = {}
                for distribution in distributions_to_plot:
                    selected_dist = distributions[distribution]
                    # Используем сохраненные параметры вместо повторного вычисления
                    params = distribution_params[distribution]
                    teor_label = distribution
                    custom_dict[teor_label] = selected_dist.ppf(1-p/100, *params)
                custom_df = pd.DataFrame.from_dict(custom_dict, orient='index', columns=['Values'])
                st.markdown(custom_df.to_html(index=True, header=False), unsafe_allow_html=True)
            
            with st.expander("📋 Параметры и метрики качества полученных распределений", expanded=False):
                def get_green_red_gradient_color(value):
                    if value <= 0.5:
                        # Зеленый (#63be7b) → Прозрачный
                        progress = value / 0.5
                        r, g, b = 99, 190, 123  # Зеленый
                        alpha = 1 - progress
                    else:
                        # Прозрачный → Красный (#f8696b)
                        progress = (value - 0.5) / 0.5
                        r, g, b = 248, 105, 107  # Красный
                        alpha = progress
                    return f'rgba({r}, {g}, {b}, {alpha})'
                
                def style_dataframe(df):
                    styler = df.style
                    
                    # Функция для первых 3 столбцов (отклонение от первой строки)
                    def style_first_three(col):
                        if col.name in df.columns[:3]:
                            colors = [''] * len(col)  # Первая строка без заливки
                            
                            # Если всего 2 строки или меньше - не заливаем
                            if len(col) <= 2:
                                return colors
                            
                            base_value = float(col.iloc[0])  # Гарантированно числовое
                            
                            # Собираем числовые значения кроме первой строки
                            numeric_data = []
                            for i in range(1, len(col)):
                                val = col.iloc[i]
                                if isinstance(val, (int, float, np.number)) and pd.notna(val):
                                    numeric_data.append((i, float(val)))
                            
                            # Нужно минимум 2 значения для сравнения (чтобы было самое близкое и самое далекое)
                            if len(numeric_data) < 2:
                                return colors
                            
                            # Находим минимальное и максимальное отклонение от базового значения
                            deviations = [abs(val - base_value) for _, val in numeric_data]
                            min_deviation = min(deviations)
                            max_deviation = max(deviations)
                            
                            # Если все значения одинаковые (min == max), то все будут зелеными
                            if max_deviation == min_deviation:
                                for i, _ in numeric_data:
                                    colors[i] = f'background-color: {get_green_red_gradient_color(0.0)}'  # Зеленый
                            else:
                                # Нормализуем отклонения от 0 до 1, где 0 - минимальное отклонение (зеленый), 1 - максимальное (красный)
                                for (i, val), deviation in zip(numeric_data, deviations):
                                    normalized = (deviation - min_deviation) / (max_deviation - min_deviation)
                                    colors[i] = f'background-color: {get_green_red_gradient_color(normalized)}'
                            
                            return colors
                        return [''] * len(col)
                                        
                    # Функция для 4 столбца (чем больше значение, тем менее красный)
                    def style_fourth(col):
                        if col.name == df.columns[3]:
                            colors = [''] * len(col)
                            numeric_values = []
                            
                            for i, val in enumerate(col):
                                if isinstance(val, (int, float, np.number)) and pd.notna(val):
                                    numeric_values.append((i, float(val)))
                            
                            if len(numeric_values) >= 2:
                                values = [val for _, val in numeric_values]
                                max_val = max(values)
                                min_val = min(values)
                                
                                if max_val > min_val:
                                    for i, val in numeric_values:
                                        # Инвертируем: чем больше значение, тем меньше красного
                                        normalized = 1 - ((val - min_val) / (max_val - min_val))
                                        colors[i] = f'background-color: {get_green_red_gradient_color(normalized)}'
                            
                            return colors
                        return [''] * len(col)
                    
                    # Функция для 5, 6, 7 столбца (чем меньше значение, тем ярче)
                    def style_fifth_sixth_seventh(col):
                        if col.name in df.columns[4:7]:  # MAE, maxE, A-D
                            colors = [''] * len(col)
                            numeric_values = []
                            
                            for i, val in enumerate(col):
                                if isinstance(val, (int, float, np.number)) and pd.notna(val):
                                    numeric_values.append((i, float(val)))
                            
                            if len(numeric_values) >= 2:
                                values = [val for _, val in numeric_values]
                                max_val = max(values)
                                min_val = min(values)
                                
                                if max_val > min_val:
                                    for i, val in numeric_values:
                                        # Чем меньше значение, тем больше красного (инвертируем нормализацию)
                                        normalized = ((val - min_val) / (max_val - min_val))
                                        colors[i] = f'background-color: {get_green_red_gradient_color(normalized)}'
                            
                            return colors
                        return [''] * len(col)
                    
                    # Применяем стили ко всем столбцам
                    styler = styler.apply(style_first_three, axis=0)
                    styler = styler.apply(style_fourth, axis=0)
                    styler = styler.apply(style_fifth_sixth_seventh, axis=0)
                    
                    return styler
                
                parameters_df.set_index('Распределение' ,drop=True, inplace=True)
                parameters_df = parameters_df.T
                styled_df = style_dataframe(parameters_df)
                st.markdown(styled_df.to_html(index=True, header=True), unsafe_allow_html=True)
                if len(parameters_df) >= 2:
                    st.markdown("""
                                <b>Примечания к таблице:</b>
                                <br>
                                &nbsp;&nbsp;&nbsp;&nbsp;Зелёным цветом показаны значения, ближайшие к эмпирическим, красным - самые удалённые.
                                """, unsafe_allow_html=True)
                st.markdown("""
                            <b>Расшифровка названий столбцов:</b>
                            <br>
                            &nbsp;&nbsp;&nbsp;&nbsp;• <b>Среднее</b> - среднее значение
                            <br>
                            &nbsp;&nbsp;&nbsp;&nbsp;• <b>Cv</b> - коэффициент вариации
                            <br>
                            &nbsp;&nbsp;&nbsp;&nbsp;• <b>Cs</b> - коэффициент асимметрии
                            <br>
                            &nbsp;&nbsp;&nbsp;&nbsp;• <b>R²</b> - коэффициент детерминации (чем ближе к 1, тем лучше модель описывает изменения в наблюдаемых данных)
                            <br>
                            &nbsp;&nbsp;&nbsp;&nbsp;• <b>MAE</b> - средняя абсолютная ошибка (среднее отклонение предсказаний от эмпирических данных)
                            <br>
                            &nbsp;&nbsp;&nbsp;&nbsp;• <b>maxE</b> - максимальная абсолютная ошибка (максимальное отклонение предсказаний от эмпирических данных)
                            <br>
                            &nbsp;&nbsp;&nbsp;&nbsp;• <b>A-D</b> - Критерий согласия Андерсона-Дарлинга (чем меньше, тем лучше соответствие распределения данным)
                            """, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Ошибка: {str(e)}")
