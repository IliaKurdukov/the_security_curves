"""Точка входа Streamlit: UI кривых обеспеченности."""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy.stats as stats
import streamlit as st
from sklearn.metrics import mean_absolute_error, max_error, r2_score

from analytics import log_analytics, update_analytics_file_rows
from distributions import (
    CustomDistributionAdapter,
    KrytskyMenkelAdapter,
    LMomentsDistributionAdapter,
    ScipyDistributionAdapter,
    anderson_darling_test,
    build_distributions,
    create_scipy_dist_from_lmoments,
    format_stat,
    km_coefficient_of_skewness,
    km_coefficient_of_variation,
)
from excel_io import read_excel

ru_dict = {
    "page_title": "Кривые обеспеченности",
    "title": "📉 Кривые обеспеченности",
}

st.set_page_config(
    page_title=ru_dict["page_title"],
    page_icon="📉",
    layout="wide",
    menu_items={"About": "Приложение для анализа экстремальных событий"},
)

st.title(ru_dict["title"])

st.sidebar.markdown(
    """
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
"""
)


def pluralize_rows(number: int) -> str:
    if number % 10 == 1 and number % 100 != 11:
        return "строку"
    if 2 <= number % 10 <= 4 and (number % 100 < 10 or number % 100 >= 20):
        return "строки"
    return "строк"


def detect_decimal_precision(series):
    """Сколько знаков после запятой у исходных данных (минимум 1, как раньше)."""
    max_prec = 0
    saw_fraction = False
    for val in series.dropna():
        if isinstance(val, (int, np.integer)):
            continue
        if isinstance(val, float) and val.is_integer():
            continue
        saw_fraction = True
        text = str(val)
        if "." in text:
            # убрать хвост научной записи, если вдруг
            frac = text.split(".")[1]
            frac = frac.split("e")[0].split("E")[0]
            max_prec = max(max_prec, len(frac))
    return max_prec if saw_fraction else 1


def custom_round(x, min_decimals=None):
    """
    Округление метрик: 3 значащие цифры; при |x| >= 100 — до целого.
    min_decimals — не грубее точности исходного ряда (для среднего, MAE, maxE).
    """
    x = float(x)
    abs_x = abs(x)

    if abs_x >= 100:
        decimals = 0
    elif abs_x == 0:
        decimals = 0
    else:
        text = np.format_float_positional(x, precision=3, fractional=False, trim="-")
        decimals = len(text.split(".")[1]) if "." in text else 0

    if min_decimals is not None:
        decimals = max(decimals, int(min_decimals))

    return f"{x:.{decimals}f}"


def get_green_red_gradient_color(value):
    if value <= 0.5:
        progress = value / 0.5
        r, g, b = 99, 190, 123
        alpha = 1 - progress
    else:
        progress = (value - 0.5) / 0.5
        r, g, b = 248, 105, 107
        alpha = progress
    return f"rgba({r}, {g}, {b}, {alpha})"


def _is_number(val):
    return isinstance(val, (int, float, np.number)) and pd.notna(val)


def _colors_first_three(col):
    colors = [""] * len(col)
    if len(col) <= 2:
        return colors

    base_value = float(col.iloc[0])
    numeric_data = [
        (i, float(col.iloc[i]))
        for i in range(1, len(col))
        if _is_number(col.iloc[i])
    ]
    if len(numeric_data) < 2:
        return colors

    deviations = [abs(val - base_value) for _, val in numeric_data]
    min_deviation = min(deviations)
    max_deviation = max(deviations)

    if max_deviation == min_deviation:
        for i, _ in numeric_data:
            colors[i] = f"background-color: {get_green_red_gradient_color(0.0)}"
    else:
        for (i, _), deviation in zip(numeric_data, deviations):
            normalized = (deviation - min_deviation) / (max_deviation - min_deviation)
            colors[i] = f"background-color: {get_green_red_gradient_color(normalized)}"
    return colors


def _colors_higher_better(col):
    colors = [""] * len(col)
    numeric_values = [
        (i, float(val)) for i, val in enumerate(col) if _is_number(val)
    ]
    if len(numeric_values) < 2:
        return colors
    values = [val for _, val in numeric_values]
    max_val, min_val = max(values), min(values)
    if max_val > min_val:
        for i, val in numeric_values:
            normalized = 1 - ((val - min_val) / (max_val - min_val))
            colors[i] = f"background-color: {get_green_red_gradient_color(normalized)}"
    return colors


def _colors_lower_better(col):
    colors = [""] * len(col)
    numeric_values = [
        (i, float(val)) for i, val in enumerate(col) if _is_number(val)
    ]
    if len(numeric_values) < 2:
        return colors
    values = [val for _, val in numeric_values]
    max_val, min_val = max(values), min(values)
    if max_val > min_val:
        for i, val in numeric_values:
            normalized = (val - min_val) / (max_val - min_val)
            colors[i] = f"background-color: {get_green_red_gradient_color(normalized)}"
    return colors


def style_dataframe_html(df, data_precision=None):
    """Цветная HTML-таблица без pandas Styler (не нужен jinja2)."""
    n_rows, n_cols = df.shape
    cell_styles = [[""] * n_cols for _ in range(n_rows)]

    for j, col_name in enumerate(df.columns):
        col = df.iloc[:, j]
        if j < 3:
            colors = _colors_first_three(col)
        elif j == 3:
            colors = _colors_higher_better(col)
        elif j < 7:
            colors = _colors_lower_better(col)
        else:
            colors = [""] * n_rows
        for i, style in enumerate(colors):
            cell_styles[i][j] = style

    # Среднее (0), MAE (4), maxE (5) — в единицах исходного ряда
    data_scale_cols = {0, 4, 5}

    def fmt(val, col_idx=None):
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return ""
        if (
            isinstance(val, (int, float, np.number))
            and not isinstance(val, (bool, np.bool_))
            and pd.notna(val)
            and not np.isinf(val)
        ):
            min_decimals = (
                data_precision if col_idx in data_scale_cols else None
            )
            return str(custom_round(float(val), min_decimals=min_decimals))
        return str(val)

    parts = ["<table>", "<thead><tr><th></th>"]
    for col in df.columns:
        parts.append(f"<th>{col}</th>")
    parts.append("</tr></thead><tbody>")

    for i, (idx, row) in enumerate(df.iterrows()):
        parts.append(f"<tr><th>{idx}</th>")
        for j, val in enumerate(row):
            style = cell_styles[i][j]
            attr = f' style="{style}"' if style else ""
            parts.append(f"<td{attr}>{fmt(val, col_idx=j)}</td>")
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "".join(parts)


uploaded_file = st.file_uploader("Загрузите Excel файл", type=["xls", "xlsx", "xlsm"])
if uploaded_file:
    try:
        df = read_excel(uploaded_file)
        st.success(
            f"Данные успешно загружены и содержат {len(df)} {pluralize_rows(len(df))}"
        )
        log_analytics(uploaded_file=uploaded_file)
        update_analytics_file_rows(len(df))
        with st.expander("🔢 Фрагмент загруженных данных", expanded=False):
            st.markdown(df.head().to_html(), unsafe_allow_html=True)

        numeric_cols = df.select_dtypes(include=["number"]).columns
        cols = df.columns.tolist()
        if len(numeric_cols) == 0:
            st.error("В файле нет числовых столбцов")
            st.stop()

        values_col = st.selectbox(
            "Выберите столбец с данными для построения кривой обеспеченности",
            numeric_cols,
        )
        df.rename(columns={values_col: str(values_col)}, inplace=True)

        null_count = df[values_col].isna().sum()
        if null_count > 0:
            st.markdown(
                "В данных обнаружены и удалены для работы пропуски в следующих строках:"
            )
            st.markdown(df[df[values_col].isna()].to_html(), unsafe_allow_html=True)
            df = df.dropna(subset=[values_col])

        cols.insert(0, "Без группировки")
        index_col = st.selectbox("Выберите столбец для группировки данных", cols)
        if index_col != "Без группировки":
            aggfunc = st.selectbox(
                "Выберите способ группировки данных",
                ["Максимальные значения", "Средние значения", "Минимальные значения"],
            )
            df.rename(columns={index_col: str(index_col)}, inplace=True)

        with st.expander(
            "🔢 Хронологический ряд значений и эмпирическое распределение",
            expanded=False,
        ):
            if index_col != "Без группировки":
                aggfunc_dict = {
                    "Максимальные значения": "max",
                    "Средние значения": "mean",
                    "Минимальные значения": "min",
                }
                data = df.pivot_table(
                    index=index_col, values=values_col, aggfunc=aggfunc_dict[aggfunc]
                )
            else:
                data = df[values_col]
            data = pd.DataFrame(data)
            n = len(data)
            data["Ранг"] = np.arange(1, n + 1)
            max_rank_plus_one = n + 1
            data["Вероятность"] = data["Ранг"] / max_rank_plus_one
            data["Обеспеченность P, %"] = round(data["Вероятность"] * 100, 2)
            if index_col != "Без группировки":
                data[index_col] = data.index
            data_to_merge = data.sort_values(by=values_col, ascending=False)
            data_to_merge.drop(
                ["Вероятность", "Обеспеченность P, %", "Ранг"], axis=1, inplace=True
            )
            data_to_merge.rename(columns={values_col: values_col + " (P)"}, inplace=True)
            if index_col != "Без группировки":
                data_to_merge.rename(
                    columns={index_col: index_col + " (P)"}, inplace=True
                )
                data_to_merge[index_col + " (P)"] = data_to_merge.index
            data_to_merge["Ранг"] = np.arange(1, n + 1)
            data = data.merge(data_to_merge, on="Ранг")
            data.set_index("Ранг", inplace=True)
            if index_col != "Без группировки":
                st.markdown(
                    data[
                        [
                            index_col,
                            values_col,
                            "Обеспеченность P, %",
                            values_col + " (P)",
                            index_col + " (P)",
                        ]
                    ].to_html(),
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    data[[values_col, "Обеспеченность P, %", values_col + " (P)"]].to_html(),
                    unsafe_allow_html=True,
                )

        with st.expander("📊 График хода значений", expanded=False):
            fig, ax = plt.subplots(figsize=(4, 2))
            x = data[index_col] if index_col != "Без группировки" else data.index
            y = data[values_col]
            plt.plot(x, y, linewidth=0.5)
            ax.set_ylabel(values_col, fontsize=5)
            ax.set_title("График хода значений", fontsize=6)
            ax.tick_params(axis="x", labelsize=5)
            ax.tick_params(axis="y", labelsize=5)
            st.pyplot(fig, width="content")

        data = data.sort_values(by=values_col)

        data_min = data[values_col].min()
        data_max = data[values_col].max()
        distributions = build_distributions(data_min, data_max)

        st.markdown(
            """
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
            """,
            unsafe_allow_html=True,
        )

        distributions_to_plot = st.multiselect(
            "",
            distributions,
            default=[list(distributions)[-1]],
            label_visibility="collapsed",
        )
        if distributions_to_plot:
            log_analytics(
                uploaded_file=uploaded_file,
                distributions_selected=distributions_to_plot,
            )

        def scalefunc(x):
            return stats.norm.ppf(x / 100, loc=0, scale=1)

        fig, ax = plt.subplots(figsize=(4, 2))

        x = data["Вероятность"] * 100
        y = data[values_col + " (P)"]
        plt.scatter(
            x,
            y,
            label="Эмпирическое",
            s=5,
            facecolors="none",
            edgecolors="black",
            linewidths=0.5,
        )

        percent_list_1 = [
            0.01,
            0.1,
            0.33,
            0.5,
            1,
            2,
            3,
            5,
            10,
            50,
            63,
            90,
            95,
            98,
            99,
            99.9,
        ]
        df_1 = pd.DataFrame(percent_list_1, columns=["Обеспеченность"])

        parameters = ["Среднее", "Cv", "Cs", "R²", "MAE", "maxE", "A-D"]
        parameters_df = pd.DataFrame(parameters, columns=["Распределение"])
        mean = data[values_col].mean()
        std = data[values_col].std()
        cv = std / mean
        cs = stats.skew(data[values_col])
        parameters_df["Эмпирическое"] = pd.DataFrame([mean, cv, cs, "-", "-", "-", "-"])

        sample = df.loc[0, values_col]
        if isinstance(sample, (int, np.integer)) or (
            isinstance(sample, float) and sample.is_integer()
        ):
            precision = 1
        else:
            sample_str = str(sample)
            if "." in sample_str:
                precision = len(sample_str.split(".")[1])
            else:
                precision = 1
        # Точность по всему столбцу (не грубее, чем у исходных данных)
        precision = max(precision, detect_decimal_precision(df[values_col]))

        distribution_params = {}
        distribution_objects = {}

        range1 = np.arange(0.1, 1.1, 0.2)
        range2 = np.arange(1.1, 2.0, 0.3)
        range3 = np.arange(2.0, 98.0, 1.0)
        range4 = np.arange(98.0, 98.9, 0.3)
        range5 = np.arange(98.9, 99.9, 0.2)
        x_teor = np.concatenate([range1, range2, range3, range4, range5, [99.9]])

        for distribution in distributions_to_plot:
            selected_dist = distributions[distribution]
            params = selected_dist.fit(data[values_col])
            distribution_params[distribution] = params

            predict = data["Вероятность"].apply(
                lambda x, dist=selected_dist, p=params: dist.ppf(1 - x, *p)
            )
            r2 = r2_score(data[values_col + " (P)"], predict)
            mae = mean_absolute_error(data[values_col + " (P)"], predict)
            maxE = max_error(data[values_col + " (P)"], predict)

            try:
                if isinstance(selected_dist, ScipyDistributionAdapter):
                    fitted_dist = selected_dist._dist(*params)
                    distribution_objects[distribution] = fitted_dist
                    cdf_func = fitted_dist.cdf
                elif isinstance(selected_dist, LMomentsDistributionAdapter):
                    fitted_dist = create_scipy_dist_from_lmoments(
                        selected_dist._lmoments_name, params
                    )
                    distribution_objects[distribution] = fitted_dist
                    cdf_func = fitted_dist.cdf
                elif (
                    isinstance(selected_dist, CustomDistributionAdapter)
                    and "Гумбеля (Мом)" in distribution
                ):
                    fitted_dist = stats.gumbel_r(loc=params[0], scale=params[1])
                    distribution_objects[distribution] = fitted_dist
                    cdf_func = fitted_dist.cdf
                elif isinstance(selected_dist, KrytskyMenkelAdapter):
                    cdf_func = lambda x, dist=selected_dist, p=params: dist.cdf_original(
                        x, *p
                    )
                elif isinstance(selected_dist, CustomDistributionAdapter):

                    def cdf_func(x, dist_name=distribution, p=params):
                        return np.nan

                ad_stat = anderson_darling_test(data[values_col].values, cdf_func)

            except Exception as e:
                st.warning(
                    f"Не удалось рассчитать A-D статистику для {distribution}: {str(e)}"
                )
                ad_stat = np.nan

            def f(x, dist=selected_dist, p=params):
                return dist.ppf(1 - x / 100, *p)

            f2 = np.vectorize(f)
            teor_label = distribution
            plt.plot(x_teor, f2(x_teor), label=teor_label, linewidth=0.7)

            df_1[f"{teor_label}"] = df_1["Обеспеченность"].apply(
                lambda x, dist=selected_dist, p=params: round(
                    dist.ppf(1 - x / 100, *p), precision
                )
            )

            if isinstance(selected_dist, ScipyDistributionAdapter):
                if distribution in distribution_objects:
                    dist = distribution_objects[distribution]
                else:
                    dist = selected_dist._dist(*params)
                mean = dist.mean()
                std = dist.std()
                cv = format_stat(std / mean)
                cs = format_stat(dist.stats(moments="s"))
            elif isinstance(selected_dist, LMomentsDistributionAdapter):
                try:
                    if distribution in distribution_objects:
                        dist = distribution_objects[distribution]
                    else:
                        dist = create_scipy_dist_from_lmoments(
                            selected_dist._lmoments_name, params
                        )

                    mean = dist.mean()
                    std = dist.std()
                    cv = format_stat(std / mean)
                    cs = format_stat(dist.stats(moments="s"))
                except Exception as e:
                    st.warning(
                        f"Ошибка при расчете статистик для {distribution}: {str(e)}"
                    )
                    mean = "Ошибка"
                    cv = "Ошибка"
                    cs = "Ошибка"
            elif isinstance(selected_dist, KrytskyMenkelAdapter):
                try:
                    γ, a, b = params
                    mean = selected_dist.mean_original(γ, a, b)
                    cv = format_stat(km_coefficient_of_variation(γ, a, b))
                    cs = format_stat(km_coefficient_of_skewness(γ, a, b))
                except Exception as e:
                    st.warning(
                        f"Ошибка при расчете статистик для {distribution}: {str(e)}"
                    )
                    mean = "Ошибка"
                    cv = "Ошибка"
                    cs = "Ошибка"
            elif (
                isinstance(selected_dist, CustomDistributionAdapter)
                and "Гумбеля (Мом)" in distribution
            ):
                try:
                    dist = stats.gumbel_r(loc=params[0], scale=params[1])
                    mean = dist.mean()
                    std = dist.std()
                    cv = format_stat(std / mean)
                    cs = format_stat(dist.stats(moments="s"))
                except Exception as e:
                    st.warning(
                        f"Ошибка при расчете статистик для {distribution}: {str(e)}"
                    )
                    mean = "Ошибка"
                    cv = "Ошибка"
                    cs = "Ошибка"

            parameters_df[f"{teor_label}"] = pd.DataFrame(
                [mean, cv, cs, r2, mae, maxE, ad_stat]
            )

        ax.xaxis.grid(True)
        plt.xscale("function", functions=[scalefunc, lambda x: x])
        ax.set_xlabel("Обеспеченность, %", fontsize=5)
        ax.set_ylabel(values_col, fontsize=5)
        ax.set_title("Значения с разной долей обеспеченности", fontsize=6)
        ax.set(xlim=(0.1, 99.9))
        plt.xticks([0.1, 1, 2, 5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 98, 99, 99.9])
        ax.set_xticklabels(
            [0.1, 1, 2, 5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 98, 99, 99.9]
        )
        plt.legend(title="Вид распределения")
        ax.tick_params(axis="x", labelsize=5)
        ax.tick_params(axis="y", labelsize=5)
        legend = ax.legend(fontsize=5)
        st.pyplot(fig, width="content")

        with st.expander(
            "📋 Расчет значений с разной долей обеспеченности (в %)", expanded=False
        ):
            df_1 = df_1.T
            st.markdown(df_1.to_html(index=True, header=False), unsafe_allow_html=True)

            p = st.number_input(
                "Выберите обеспеченность для расчета значения (0 < P < 100)",
                min_value=0.001,
                max_value=99.999,
                format="%.3f",
            )
            if (
                "last_logged_p" not in st.session_state
                or st.session_state.last_logged_p != p
            ):
                log_analytics(
                    uploaded_file=uploaded_file,
                    distributions_selected=distributions_to_plot,
                    custom_ensurence_value=p,
                )
                st.session_state.last_logged_p = p

            custom_dict = {}
            for distribution in distributions_to_plot:
                selected_dist = distributions[distribution]
                params = distribution_params[distribution]
                teor_label = distribution
                custom_dict[teor_label] = selected_dist.ppf(1 - p / 100, *params)
            custom_df = pd.DataFrame.from_dict(
                custom_dict, orient="index", columns=["Values"]
            )
            st.markdown(
                custom_df.to_html(index=True, header=False), unsafe_allow_html=True
            )

        with st.expander(
            "📋 Параметры и метрики качества полученных распределений", expanded=False
        ):
            parameters_df = parameters_df.set_index("Распределение", drop=True).T
            st.markdown(
                style_dataframe_html(parameters_df, data_precision=precision),
                unsafe_allow_html=True,
            )
            if len(parameters_df) >= 2:
                st.markdown(
                    """
                                <b>Примечания к таблице:</b>
                                <br>
                                &nbsp;&nbsp;&nbsp;&nbsp;Зелёным цветом показаны значения, ближайшие к эмпирическим, красным - самые удалённые.
                                """,
                    unsafe_allow_html=True,
                )
            st.markdown(
                """
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
                            """,
                unsafe_allow_html=True,
            )

    except Exception as e:
        st.error(f"Ошибка: {str(e)}")
