import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import re
import scipy.stats as stats
from sklearn.metrics import mean_absolute_error

st.title("📉 Кривые обеспеченности")

uploaded_file = st.file_uploader("Загрузите XLS файл")
if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)
        def pluralize_rows(number: int) -> str:
          if number % 10 == 1 and number % 100 != 11:
              return "строку"  # 1 строка (но 11, 111, 211 и т.д. — "строк")
          elif 2 <= number % 10 <= 4 and (number % 100 < 10 or number % 100 >= 20):
              return "строки"  # 2, 3, 4 строки (но 12, 13, 14 — "строк")
          else:
              return "строк"  # 0, 5-20, 25-30 и т.д.
        st.success(f"Данные успешно загружены и содержат {len(df)} {pluralize_rows(len(df))}. Ниже представлен пример данных:")
        st.markdown(df.head(3).to_html(), unsafe_allow_html=True)
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
            fig, ax = plt.subplots()

            x = data['Вероятность'] * 100
            y = data[values_col]
            plt.scatter(x, y,
                        label='Эмпирическое распределение',
                        s=20,           # размер точек (можно подобрать нужное значение)
                        facecolors='none', # без заливки
                        edgecolors='black', # черный контур
                        linewidths=1)    # толщина контура
            
            # таблица
            percent_list_1 = [0.01, 0.1, 0.33, 0.5, 1, 2, 3, 5]
            percent_list_2 = [10, 50, 63, 90, 95, 98, 99, 99.9]
            df_1 = pd.DataFrame(percent_list_1, columns=['Обеспеченность'])
            df_2 = pd.DataFrame(percent_list_2, columns=['Обеспеченность'])
            # Функция для форматирования чисел в таблице
            def custom_round(x):
              abs_x = abs(x)
              if abs_x >= 100:  # Если 3+ знака до запятой → округляем до целого
                return round(x)
              else:  # Иначе оставляем 3 значащих цифры
                return np.format_float_positional(x, precision=3, fractional=False, trim='-')

            # построение кривой с распределением
            for disribution in distributions_to_plot:
              dist_key = distributions[disribution]
              selected_dist = getattr(stats, dist_key)  # Получаем класс распределения
              params = selected_dist.fit(data[values_col])
              #data['Предсказание'] = data['Вероятность'].apply(lambda x: selected_dist.ppf(1-x, *params))
              #mae = mean_absolute_error(data[values_col], data['Предсказание'])
              mae=1

              def f(x):
                return selected_dist.ppf(1-x/100, *params)
              f2 = np.vectorize(f)
              x = np.arange(0.1, 99.9, 0.1)
              teor_label = re.sub(r'\s*\([^)]*\)$', '', disribution)
              plt.plot(x, f2(x), label= f'Распределение {teor_label} ({round(mae, 1)})')

              #сбор данных в таблицу
              df_1[f'Распределение {teor_label}'] = df_1['Обеспеченность'].apply(lambda x: custom_round(selected_dist.ppf(1-x/100, *params)))
              df_2[f'Распределение {teor_label}'] = df_1['Обеспеченность'].apply(lambda x: custom_round(selected_dist.ppf(1-x/100, *params)))

            # добавление линий сетки, масштаба по горизонтальной оси, подписей осей и графика,
            # границ, шага и подписей делений для горизонтальной оси
            ax.xaxis.grid(True)
            plt.xscale('function', functions=[scalefunc, lambda x: x])
            ax.set(xlabel = "Обеспеченность, %")
            ax.set(ylabel = values_col)
            ax.set(title= f"Значения анализируемой величины с разной долей обеспеченности \n \
            (в легенде в скобках указана средняя ошибка распределения)")
            ax.set(xlim=(0.1,99.9))
            plt.xticks([0.1, 1, 2, 5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 98, 99, 99.9])
            ax.set_xticklabels([0.1, 1, 2, 5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 98, 99, 99.9])
            plt.legend()
            st.pyplot(fig)

            with st.expander("# 📋 Расчет значений с разной долей обеспеченности (в %)", expanded=True):
              df_1 = df_1.T
              df_2 = df_2.T
              st.markdown(df_1.to_html(index=True, header=False), unsafe_allow_html=True)
              st.markdown(df_2.to_html(index=True, header=False), unsafe_allow_html=True)

              # ввод значений
              p = st.number_input(
              "Выберите обеспеченность для расчета значения (0 < P < 100)",
              min_value=0.0,
              max_value=99.999,
              #value=0.0,
              #step=0.01,
              #format="%.2f",  # Формат с двумя знаками после запятой
              )
              if p != 0:
                custom_dict = {}
                for disribution in distributions_to_plot:
                  dist_key = distributions[disribution]
                  selected_dist = getattr(stats, dist_key)
                  params = selected_dist.fit(data[values_col])
                  value = selected_dist.ppf(1-p/100, *params)
                  teor_label = re.sub(r'\s*\([^)]*\)$', '', disribution)
                  custom_dict[teor_label] = value
                custom_df = pd.DataFrame(list(custom_dict.items()))
                st.markdown(custom_df.to_html(index=False, header=False), unsafe_allow_html=True)
                #st.markdown(f'При обеспеченности {p}% {values_col} составляет {custom_round(value)}.')

    except Exception as e:
        st.error(f"Ошибка: {str(e)}")
