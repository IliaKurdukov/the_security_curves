import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import scipy.stats as stats

st.title("📊 Построение кривых обеспеченности")

uploaded_file = st.file_uploader("Загрузите XLS файл")
if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)
        st.success(f"Данные успешно загружены и содержат {len(df)} строк. \n\n Ниже представлен пример данных:")
        st.table(df.sample(5))
        #st.write(result['notes'])
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
            data['Вероятность'] = 1 - (data['Ранг'] + 1) / (pivot_df['Ранг'].max() + 1)

            distributions = {'Гумбеля': 'gumbel_r', 'Фреше': 'genextreme', 'Пирсона 3 типа': 'pearson3'}
            disribution = st.selectbox("Выберите распределение для аппроксимации", distributions)
            dist_key = distributions[disribution]
            selected_dist = getattr(stats, dist_key)  # Получаем класс распределения

            # Пример вычисления PDF (функции плотности)
            data_points = np.linspace(-3, 3, 100)
            pdf_values = selected_dist.pdf(data_points, *params)  # params - параметры распределения

            # инициализация функции для изменения масштаба по горизонтальной оси
            def scalefunc(x):
              return stats.norm.ppf(x/100, loc=0, scale=1)

            # График
            fig, ax = plt.subplots()
            params = selected_dist.fit(data[values_col])

            x = data['Вероятность'] * 100
            y = data['Высота']
            plt.scatter(x, y, label='Эмпирическое распределение')

            # построение кривой с распределением
            def f(x):
                return selected_dist.ppf(1-x/100, params)
            f2 = np.vectorize(f)
            x = np.arange(0.1, 99.9, 0.1)
            plt.plot(x, f2(x), color = 'red', label='Теоретическое распределение')

            # добавление линий сетки, масштаба по горизонтальной оси, подписей осей и графика,
            # границ, шага и подписей делений для горизонтальной оси
            ax.xaxis.grid(True)
            plt.xscale('function', functions=[scalefunc, lambda x: x])
            ax.set(xlabel="Обеспеченность, %")
            ax.set(ylabel="Инализируемая величина")
            ax.set(title="Значения анализируемой величины с разной долей обеспеченности")
            ax.set(xlim=(0.1,99.9))
            plt.xticks([0.1, 1, 2, 5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 98, 99, 99.9])
            ax.set_xticklabels([0.1, 1, 2, 5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 98, 99, 99.9])
            plt.legend()
            st.pyplot(fig)

    except Exception as e:
        st.error(f"Ошибка: {str(e)}")
