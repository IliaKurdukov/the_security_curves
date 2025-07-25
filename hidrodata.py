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
        st.success(f"Данные успешно загружены и содержат {len(df)} строк. \n\n Ниже представлен пример данных:")
        #st.table(df.sample(3))
        st.markdown(df.sample(3).to_html(), unsafe_allow_html=True)
        # Автоматическое определение столбцов
        numeric_cols = df.select_dtypes(include=['number']).columns
        cols = df.columns.tolist()
        if len(numeric_cols) == 0:
            st.error("В файле нет числовых столбцов")
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
                             'Фреше (метод максимального правдоподобия)': 'genextreme',
                             'Пирсона 3 типа (метод максимального правдоподобия)': 'pearson3'}
            disribution = st.selectbox("Выберите распределение для аппроксимации", distributions)
            dist_key = distributions[disribution]
            selected_dist = getattr(stats, dist_key)  # Получаем класс распределения
            params = selected_dist.fit(data[values_col])
            data['Предсказание'] = data['Вероятность'].apply(lambda x: selected_dist.ppf(1-x, *params))
            mae = mean_absolute_error(data[values_col], data['Предсказание'])

            # инициализация функции для изменения масштаба по горизонтальной оси
            def scalefunc(x):
              return stats.norm.ppf(x/100, loc=0, scale=1)

            # График
            fig, ax = plt.subplots()

            x = data['Вероятность'] * 100
            y = data[values_col]
            plt.scatter(x, y, label='Эмпирическое распределение')

            # построение кривой с распределением
            def f(x):
                return selected_dist.ppf(1-x/100, *params)
            f2 = np.vectorize(f)
            x = np.arange(0.1, 99.9, 0.1)
            teor_label = re.sub(r'\s*\([^)]*\)$', '', disribution)
            plt.plot(x, f2(x), color = 'red', label= f'Распределение {teor_label}')

            # добавление линий сетки, масштаба по горизонтальной оси, подписей осей и графика,
            # границ, шага и подписей делений для горизонтальной оси
            ax.xaxis.grid(True)
            plt.xscale('function', functions=[scalefunc, lambda x: x])
            ax.set(xlabel = "Обеспеченность, %")
            ax.set(ylabel = values_col)
            ax.set(title= f"Значения анализируемой величины с разной долей обеспеченности\n \
            Средняя абсолютная ошибка составляет {round(mae, 1)}")
            ax.set(xlim=(0.1,99.9))
            plt.xticks([0.1, 1, 2, 5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 98, 99, 99.9])
            ax.set_xticklabels([0.1, 1, 2, 5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 98, 99, 99.9])
            plt.legend()
            st.pyplot(fig)

            with st.expander("# 📋 Расчет значений с разной долей обеспеченности (в %)", expanded=True):

              # таблица
              percent_list = [0.01, 0.1, 0.5, 1, 2, 3, 5, 10, 50, 90, 95, 98, 99]
              df = pd.DataFrame(percent_list, columns=['Обеспеченность'])
              df['Значения'] = df['Обеспеченность'].apply(lambda x: selected_dist.ppf(1-x/100, *params))
              # Функция для форматирования чисел
              def custom_round(x):
                  abs_x = abs(x)
                  if abs_x >= 100:  # Если 3+ знака до запятой → округляем до целого
                      return round(x)
                  else:  # Иначе оставляем 3 значащих цифры
                      return np.format_float_positional(x, precision=3, fractional=False, trim='-')
              # Применяем форматирование
              df['Значения'] = df['Значения'].apply(custom_round)
              #df['Обеспеченность'] = df['Обеспеченность'].astype(str) + '%'
              #df = df.set_index("Обеспеченность")
              df = df.T
              #st.dataframe(df)
              st.markdown(df.to_html(index=False, header=False), unsafe_allow_html=True)
              #st.table(df)

              # бегунок
              p = st.number_input(
              "Выберите обеспеченность для расчета значения (0 < P < 100)",
              min_value=0.001,
              max_value=99.999,
              value=50.0,
              #step=0.01,
              #format="%.2f",  # Формат с двумя знаками после запятой
)
              value = selected_dist.ppf(1-p/100, *params)
              st.markdown(f'При обеспеченности {p}% {values_col} составляет {custom_round(value)}.')

    except Exception as e:
        st.error(f"Ошибка: {str(e)}")
