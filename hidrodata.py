import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

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
        if len(numeric_cols) == 0:
            st.error("В файле нет числовых столбцов")
        else:
            values_col = st.selectbox("Выберите столбец с данными для построения кривой обеспеченности", numeric_cols)
            cols = df.columns.tolist()
            cols.insert(0, 'Без группировки')
            index_col = st.selectbox("Выберите столбец для группировки данных", cols)
            if index_col != 'Без группировки':
              aggfunc = st.selectbox("Выберите способ группировки данных", ['Максимальные значения', 'Средние значения', 'Минимальные значения'])
              aggfunc_dict = {'Максимальные значения': 'max', 'Средние значения': 'mean', 'Минимальные значения': 'min'}
              data = df.pivot_table(index = index_col, values = values_col, aggfunc = aggfunc_dict[aggfunc])
            else:
              data = df[values_col]
            distributions = {'Гумбеля': 'gumbel_r', 'Фреше': 'genextreme', 'Пирсона 3 типа': 'pearson3'}
            disribution = st.selectbox("Выберите распределение для аппроксимации", distributions)

            # Гистограмма
            fig, ax = plt.subplots()
            ax.hist(data)
            st.pyplot(fig)

    except Exception as e:
        st.error(f"Ошибка: {str(e)}")
