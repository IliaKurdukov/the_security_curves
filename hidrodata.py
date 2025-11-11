import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import re
import scipy.stats as stats
import subprocess
import sys
import xlrd
from abc import ABC, abstractmethod
from sklearn.metrics import mean_absolute_error, r2_score, max_error
import lmoments3 as lm
from lmoments3 import distr
from scipy.optimize import minimize
from scipy.integrate import quad
import math

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
    
    # Вычисляем F(X_i)
    cdf_values = np.array([cdf_func(x) for x in sorted_data])
    
    # Избегаем log(0) и log(1)
    cdf_values = np.clip(cdf_values, 1e-12, 1 - 1e-12)
    
    # Статистика Anderson-Darling
    i = np.arange(1, n + 1)
    term = (2 * i - 1) * (np.log(cdf_values) + np.log(1 - cdf_values[::-1]))
    A2 = -n - (1/n) * np.sum(term)
    
    return A2

ru_dict = {'page_title': "Кривые обеспеченности",
           'title': "📉 Кривые обеспеченности"}
           

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
        with st.expander("# 🔢 Фрагмент загруженных данных", expanded=False):
            st.markdown(df.head().to_html(), unsafe_allow_html=True)

        # Автоматическое определение столбцов
        numeric_cols = df.select_dtypes(include=['number']).columns
        cols = df.columns.tolist()
        if len(numeric_cols) == 0:
            st.error("В файле нет числовых столбцов")
            st.stop()
        else:
            values_col = st.selectbox("Выберите столбец с данными для построения кривой обеспеченности", numeric_cols)
            cols.insert(0, 'Без группировки')
            index_col = st.selectbox("Выберите столбец для группировки данных", cols)
            if index_col != 'Без группировки':
                aggfunc = st.selectbox("Выберите способ группировки данных", ['Максимальные значения', 'Средние значения', 'Минимальные значения'])

            with st.expander("# 🔢 Хронологический ряд значений и эмпирическое распределение", expanded=False):
                if index_col != 'Без группировки':
                    aggfunc_dict = {'Максимальные значения': 'max', 'Средние значения': 'mean', 'Минимальные значения': 'min'}
                    data = df.pivot_table(index = index_col, values = values_col, aggfunc = aggfunc_dict[aggfunc])
                else:
                    data = df[values_col]
                data = pd.DataFrame(data)
                scaler = data.mean()
                data['Ранг'] = range(len(data))
                data['Ранг'] = data['Ранг'] + 1
                data['Вероятность'] = (data['Ранг']) / (data['Ранг'].max() + 1)
                data['Обеспеченность P, %'] = round(data['Вероятность'] * 100, 2)
                if index_col != 'Без группировки':
                    data[index_col] = data.index
                data_to_merge = data.sort_values(by=values_col, ascending = False)
                data_to_merge.drop(['Вероятность', 'Обеспеченность P, %', 'Ранг'], axis=1, inplace=True)
                data_to_merge.rename(columns={values_col: values_col + ' (P)'}, inplace=True)
                if index_col != 'Без группировки':
                    data_to_merge.rename(columns={index_col: index_col + ' (P)'}, inplace=True)
                    data_to_merge[index_col + ' (P)'] = data_to_merge.index
                data_to_merge['Ранг'] = range(len(data))
                data_to_merge['Ранг'] = data_to_merge['Ранг'] + 1
                data = data.merge(data_to_merge, on = 'Ранг')
                data.set_index('Ранг', inplace=True)
                if index_col != 'Без группировки':
                    st.markdown(data[[index_col, values_col, 'Обеспеченность P, %', values_col + ' (P)', index_col + ' (P)']].to_html(), unsafe_allow_html=True)
                else:
                    st.markdown(data[[values_col, 'Обеспеченность P, %', values_col + ' (P)']].to_html(), unsafe_allow_html=True)
                
            with st.expander("# 📊 График хода значений", expanded=False):
                 fig, ax = plt.subplots(figsize=(4, 2))

                 x = data[index_col] * 100
                 y = data[values_col]
                 plt.bar(x, y,
                             label='Эмпирическое',
                             edgecolors='black', # черный контур
                             linewidths=0.5)    # толщина контура
                 # добавление линий сетки, масштаба по горизонтальной оси, подписей осей и графика,
                 # границ, шага и подписей делений для горизонтальной оси
                 ax.xaxis.grid(True)
                 ax.set_ylabel(values_col, fontsize=5)       
                 ax.set_title(f"График хода значений", fontsize=6)
                 ax.tick_params(axis='x', labelsize=5)
                 ax.tick_params(axis='y', labelsize=5)
                 st.pyplot(fig, use_container_width=False)

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

            # Функция PPF для Крицкого-Менкеля (нужна для адаптера)
            def km_ppf(x, γ, a, b):
                """Квантильная функция распределения Крицкого-Менкеля"""
                from scipy.optimize import brentq
                def equation(k):
                    return km_cdf(k, γ, a, b) - x
                # Ищем корень на разумном интервале
                sol = brentq(equation, 1e-10, a * 100)
                return sol * scaler.iloc[0]  # Возвращаем в исходный масштаб
            
            distributions = {
                'Гумбеля (ММП)': DistributionFactory.scipy('gumbel_r', 'Гумбеля (ММП)'),
                'Пирсона 3 типа (ММП)': DistributionFactory.scipy('pearson3', 'Пирсона 3 типа (ММП)'),
                'Обобщенное (ММП)': DistributionFactory.scipy('genextreme', 'Обобщенное (ММП)'),
                'Крицкого-Менкеля (ММП)': DistributionFactory.custom(km_fit, km_ppf, 'Крицкого-Менкеля (ММП)'),
                'Гумбеля (L-мом)': DistributionFactory.lmoments('gum', 'Гумбеля (L-мом)'),
                'Пирсона 3 типа (L-мом)': DistributionFactory.lmoments('pe3', 'Пирсона 3 типа (L-мом)'),
                'Обобщенное (L-мом)': DistributionFactory.lmoments('gev', 'Обобщенное (L-мом)')
            }

            distributions_to_plot = st.multiselect(
                'Выберите распределение для аппроксимации',
                distributions,
                default = [list(distributions)[-1]]
            )

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
            if sample == int(sample):
                precision = 1
            else:
                precision = len(str(sample).split('.')[1])

            # построение кривой с распределением
            for distribution in distributions_to_plot:
                selected_dist = distributions[distribution]
                params = selected_dist.fit(data[values_col])
                predict = data['Вероятность'].apply(lambda x: selected_dist.ppf(1-x, *params))
                r2 = r2_score(data[values_col], predict)
                mae = mean_absolute_error(data[values_col], predict)
                maxE = max_error(data[values_col], predict)
                
                # Расчет A-D статистики
                try:
                    # Создаем CDF функцию для подобранного распределения
                    if isinstance(selected_dist, ScipyDistributionAdapter):
                        fitted_dist = selected_dist._dist(*params)
                        cdf_func = fitted_dist.cdf
                    elif isinstance(selected_dist, LMomentsDistributionAdapter):
                        # Для L-moments создаем соответствующее scipy распределение
                        if selected_dist._lmoments_name == 'gum':
                            fitted_dist = stats.gumbel_r(loc=params[0], scale=params[1])
                        elif selected_dist._lmoments_name == 'pe3':
                            fitted_dist = stats.pearson3(skew=params[0], loc=params[1], scale=params[2])
                        elif selected_dist._lmoments_name == 'gev':
                            fitted_dist = stats.genextreme(c=params[0], loc=params[1], scale=params[2])
                        cdf_func = fitted_dist.cdf
                    elif isinstance(selected_dist, CustomDistributionAdapter):
                        # Для кастомных распределений создаем обертку для CDF
                        def cdf_func(x):
                            # Для кастомных распределений нам нужно вычислить CDF вручную
                            if 'Крицкого-Менкеля' in distribution:
                                # Для Крицкого-Менкеля используем нашу функцию km_cdf
                                return km_cdf(x / scaler.iloc[0], *params)  # Нормализуем данные
                            else:
                                # Для других кастомных распределений можно добавить аналогично
                                return np.nan
                    
                    ad_stat = anderson_darling_test(data[values_col].values, cdf_func)
                    
                except Exception as e:
                    st.warning(f"Не удалось рассчитать A-D статистику для {distribution}: {str(e)}")
                    ad_stat = np.nan

                def f(x):
                    return selected_dist.ppf(1-x/100, *params)
                f2 = np.vectorize(f)
                x_teor = np.arange(0.1, 99.9, 0.2)
                teor_label = distribution
                plt.plot(x_teor, f2(x_teor), label= f'{teor_label}', linewidth=0.7)

                # сбор данных в таблицу c обеспеченностями
                df_1[f'{teor_label}'] = df_1['Обеспеченность'].apply(lambda x: round(selected_dist.ppf(1-x/100, *params), precision))

                # сбор данных в таблицу с параметрами распределения
                def format_stat(value):
                    """Форматирует статистику: заменяет nan/inf на 'Не существует'."""
                    if np.isnan(value) or np.isinf(value):
                        return "Не существует"
                    else:
                        return value

                # Для scipy распределений
                if isinstance(selected_dist, ScipyDistributionAdapter):
                    dist = selected_dist._dist(*params)
                    mean = dist.mean()
                    std = dist.std()
                    cv = format_stat(std/mean)
                    cs = format_stat(dist.stats(moments='s'))
                # Для L-moments распределений
                elif isinstance(selected_dist, LMomentsDistributionAdapter):
                    try:
                        # Создаем соответствующее scipy распределение с параметрами L-moments
                        if selected_dist._lmoments_name == 'gum':
                            # Гумбеля: loc, scale
                            dist = stats.gumbel_r(loc=params[0], scale=params[1])
                        elif selected_dist._lmoments_name == 'pe3':
                            # Пирсон 3 типа: skew, loc, scale
                            dist = stats.pearson3(skew=params[0], loc=params[1], scale=params[2])
                        elif selected_dist._lmoments_name == 'gev':
                            # Обобщенное экстремальное: c, loc, scale
                            dist = stats.genextreme(c=params[0], loc=params[1], scale=params[2])
                        
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
                        mean = km_mean(γ, a, b) * scaler.iloc[0]  # Возвращаем в исходный масштаб
                        cv = format_stat(km_coefficient_of_variation(γ, a, b))
                        cs = format_stat(km_coefficient_of_skewness(γ, a, b))
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
            st.pyplot(fig, use_container_width=False)

            with st.expander("# 📋 Расчет значений с разной долей обеспеченности (в %)", expanded=False):
                df_1 = df_1.T
                st.markdown(df_1.to_html(index=True, header=False), unsafe_allow_html=True)

                # ввод значений
                p = st.number_input(
                "Выберите обеспеченность для расчета значения (0 < P < 100)",
                min_value=0.001,
                max_value=99.999,
                format="%.3f"
                )
                custom_dict = {}
                for distribution in distributions_to_plot:
                    selected_dist = distributions[distribution]
                    params = selected_dist.fit(data[values_col])
                    teor_label = distribution
                    custom_dict[teor_label] = selected_dist.ppf(1-p/100, *params)
                custom_df = pd.DataFrame.from_dict(custom_dict, orient='index', columns=['Values'])
                st.markdown(custom_df.to_html(index=True, header=False), unsafe_allow_html=True)
            
            with st.expander("# 📋 Параметры и метрики качества полученных распределений", expanded=False):
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
