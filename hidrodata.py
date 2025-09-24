import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import re
import scipy.stats as stats
import subprocess
import sys
import xlrd
from sklearn.metrics import mean_absolute_error, r2_score

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

Пишите ваши вопросы и предложения, узнавайте актуальные новости и информацию о других проектах в области гидрометеорологии в [нашем канале](https://t.me/+g8Kjj2t8hvsxYmJi).

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

🙏 Спасибо за поддержку: Мише Самохину, Никите З., Татьяне Д., Елене Л., Марине М., Валентину Марченко, Татьяне Ш., Алмазу Х., Сергею, Ивану К.
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
              aggfunc_dict = {'Максимальные значения': 'max', 'Средние значения': 'mean', 'Минимальные значения': 'min'}
              data = df.pivot_table(index = index_col, values = values_col, aggfunc = aggfunc_dict[aggfunc])
            else:
              data = df[values_col]
            data = pd.DataFrame(data)
            scaler = data[values_col].mean()
            data['z'] = data[values_col] / scaler
            data = data.sort_values(by=values_col)
            data['Ранг'] = range(len(data))
            data['Вероятность'] = 1 - (data['Ранг'] + 1) / (data['Ранг'].max() + 2)

            distributions = {'Гумбеля (метод максимального правдоподобия)': 'gumbel_r',
                            'Фреше (метод максимального правдоподобия)': 'invweibull',
                            'Пирсона 3 типа (метод максимального правдоподобия)': 'pearson3',
                            'Обобщенное (метод максимального правдоподобия)': 'genextreme'}

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
            y = data[values_col]
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
            parameters = ['Среднее', 'Cv', 'Cs', 'R²', 'MAE']
            parameters_df = pd.DataFrame(parameters, columns=['Распределение'])
            mean = data[values_col].mean()
            std = data[values_col].std()
            cv = (std/mean)
            cs = (stats.skew(data[values_col]))
            parameters_df['Эмпирическое'] = pd.DataFrame([mean, cv, cs, '-', '-'])

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
            for disribution in distributions_to_plot:
              dist_key = distributions[disribution]
              selected_dist = getattr(stats, dist_key)
              params = selected_dist.fit(data['z'])
              predict = data['Вероятность'].apply(lambda x: selected_dist.ppf(1-x, *params) * scaler)
              r2 = r2_score(data[values_col], predict)
              mae =mean_absolute_error(data[values_col], predict)

              def f(x):
                return selected_dist.ppf(1-x/100, *params) * scaler
              f2 = np.vectorize(f)
              x = np.arange(0.1, 99.9, 0.1)
              teor_label = re.sub(r'\s*\([^)]*\)$', '', disribution)
              plt.plot(x, f2(x), label= f'{teor_label}', linewidth=0.7)

              # сбор данных в таблицу c обеспеченностями
              df_1[f'{teor_label}'] = df_1['Обеспеченность'].apply(lambda x: round(selected_dist.ppf(1-x/100, *params) * scaler, precision))

              # сбор данных в таблицу с параметрами распределения
              def format_stat(value):
                """Форматирует статистику: заменяет nan/inf на 'Не существует'."""
                if np.isnan(value) or np.isinf(value):
                    return "Не существует"
                else:
                  return value

              dist = selected_dist(*params)
              mean = dist.mean() * scaler
              std = dist.std() * scaler
              cv = format_stat(std/mean)
              cs = format_stat(dist.stats(moments='s'))
              parameters_df[f'{teor_label}'] = pd.DataFrame([mean, cv, cs, r2, mae])

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
              for disribution in distributions_to_plot:
                dist_key = distributions[disribution]
                selected_dist = getattr(stats, dist_key)
                params = selected_dist.fit(data['z'])
                teor_label = re.sub(r'\s*\([^)]*\)$', '', disribution)
                custom_dict[teor_label] = selected_dist.ppf(1-p/100, *params) * scaler
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
                    
                    # Функция для 5 столбца (чем меньше значение, тем ярче)
                    def style_fifth(col):
                        if col.name == df.columns[4]:
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
                    styler = styler.apply(style_fifth, axis=0)
                    
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
                            """, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Ошибка: {str(e)}")
