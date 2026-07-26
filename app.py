"""Точка входа Streamlit: UI кривых обеспеченности."""

import importlib
import math
from io import BytesIO
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import scipy.stats as stats
import streamlit as st
from sklearn.metrics import mean_absolute_error, max_error, r2_score

import i18n as i18n_mod
import curve_analysis as curve_analysis_mod

# Streamlit на Windows часто не перечитывает соседние модули
i18n_mod = importlib.reload(i18n_mod)
curve_analysis_mod = importlib.reload(curve_analysis_mod)

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
from report_io import build_results_docx

AGG_KEYS = i18n_mod.AGG_KEYS
dist_label = i18n_mod.dist_label
init_language_widgets = i18n_mod.init_language_widgets
pluralize_rows = i18n_mod.pluralize_rows
t = i18n_mod.t

SAMPLE_DATA_PATH = (
    Path(__file__).resolve().parent / "examples" / "tsc_sample__daily_precip.xlsx"
)
SAMPLE_VALUES_COL = "Осадки, мм"
SAMPLE_GROUP_COL = "Год"
SAMPLE_AGG_KEY = "agg_max"
# Русские имена в файле → английские только для тестового примера
SAMPLE_COL_EN = {
    "Год": "Year",
    "Месяц": "Month",
    "День": "Day",
    "Осадки, мм": "Precipitation, mm",
}

# Внутренний маркер «без группировки» (не из файла пользователя)
NO_GROUP = "__no_group__"

AGG_FUNCS = {
    "agg_max": "max",
    "agg_min": "min",
    "agg_mean": "mean",
    "agg_sum": "sum",
}


def option_index(options, preferred):
    """Индекс preferred в options, иначе 0."""
    opts = list(options)
    if preferred is not None and preferred in opts:
        return opts.index(preferred)
    return 0


def load_sample_file():
    """BytesIO с .name — как у st.file_uploader, для read_excel/analytics."""
    data = BytesIO(SAMPLE_DATA_PATH.read_bytes())
    data.name = SAMPLE_DATA_PATH.name
    return data


def sample_col(name_ru: str) -> str:
    """Имя столбца тестового файла с учётом языка UI."""
    if st.session_state.get("lang") == "en":
        return SAMPLE_COL_EN.get(name_ru, name_ru)
    return name_ru


def localize_sample_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Переименовать столбцы тестового файла при английском UI."""
    if not st.session_state.get("use_sample_data"):
        return df
    if st.session_state.get("lang") != "en":
        return df
    rename = {ru: en for ru, en in SAMPLE_COL_EN.items() if ru in df.columns}
    return df.rename(columns=rename) if rename else df


def localize_metric_value(val):
    """Переводит служебные метки в ячейках метрик."""
    if val == "Не существует" or val == "Undefined":
        return t("stat_undefined")
    if val == "Ошибка" or val == "Error":
        return t("error_label")
    return val


def series_row_labels(series_df, values_col, index_col, precision):
    """Подписи строк как в фильтре исключения: label → позиция."""
    labels = []
    label_to_pos = {}
    for pos in range(len(series_df)):
        val_txt = custom_round(
            series_df.iloc[pos][values_col], min_decimals=precision
        )
        if index_col != NO_GROUP:
            lab = f"{series_df.iloc[pos][index_col]} - {val_txt}"
        else:
            lab = str(val_txt)
        base = lab
        suffix = 2
        while lab in label_to_pos:
            lab = f"{base} ({suffix})"
            suffix += 1
        label_to_pos[lab] = pos
        labels.append(lab)
    return labels, label_to_pos


def criterion_for_series(series_df, source_df, values_col, index_col, criterion_col, agg_key):
    """Значения столбца-критерия, выровненные по строкам series_df."""
    if criterion_col is None or criterion_col not in source_df.columns:
        return None
    if index_col == NO_GROUP:
        if len(source_df) != len(series_df):
            return None
        return source_df[criterion_col].to_numpy()
    if agg_key in ("agg_max", "agg_min"):
        idx_fn = "idxmax" if agg_key == "agg_max" else "idxmin"
        row_idx = getattr(source_df.groupby(index_col)[values_col], idx_fn)()
        mapped = (
            source_df.loc[row_idx]
            .set_index(index_col)[criterion_col]
        )
    else:
        mapped = source_df.groupby(index_col)[criterion_col].first()
    return series_df[index_col].map(mapped).to_numpy()


def localize_parameters_view(parameters_df_view):
    """Подписи метрик/распределений для UI и Word."""
    from i18n import TRANSLATIONS, get_lang

    out = parameters_df_view.copy()
    lang = get_lang()

    def _row_label(idx):
        if idx == "Эмпирическое":
            return t("empirical")
        if idx in (
            t("compound_label"),
            "Составная",
            "Составное",
            "Compound",
        ):
            return t("compound_label")
        key = f"dist.{idx}"
        if key in TRANSLATIONS.get(lang, {}) or key in TRANSLATIONS["ru"]:
            return dist_label(str(idx))
        return str(idx)

    out.index = [_row_label(idx) for idx in out.index]
    rename_cols = {"Среднее": t("mean")}
    out = out.rename(columns=rename_cols)
    out.columns.name = t("distribution")
    for col in out.columns:
        out[col] = out[col].map(localize_metric_value)
    return out


def localize_quantiles_view(quantiles_df_view):
    """Подписи строк таблицы обеспеченностей."""
    from i18n import TRANSLATIONS, get_lang

    out = quantiles_df_view.copy()
    lang = get_lang()

    def _row_label(idx):
        if idx == "Обеспеченность":
            return t("ensurance")
        if idx == "Период повторяемости":
            return t("return_period")
        if idx in (
            t("compound_label"),
            "Составная",
            "Составное",
            "Compound",
        ):
            return t("compound_label")
        key = f"dist.{idx}"
        if key in TRANSLATIONS.get(lang, {}) or key in TRANSLATIONS["ru"]:
            return dist_label(str(idx))
        return str(idx)

    out.index = [_row_label(idx) for idx in out.index]
    return out


def with_return_period_row(df_1):
    """Добавляет столбец периода повторяемости (T=100/P) сразу после Обеспеченность."""
    periods = [
        curve_analysis_mod.format_return_period(p) for p in df_1["Обеспеченность"]
    ]
    out = df_1.copy()
    if "Период повторяемости" in out.columns:
        out["Период повторяемости"] = periods
    else:
        out.insert(1, "Период повторяемости", periods)
    return out


def linked_exceedance_inputs(key_prefix, default_p=20.0):
    """
    Два связанных поля: обеспеченность P и период повторяемости T=100/P.
    Возвращает текущее P.
    """
    p_key = f"{key_prefix}_p"
    t_key = f"{key_prefix}_t"
    if p_key not in st.session_state:
        st.session_state[p_key] = float(default_p)
    if t_key not in st.session_state:
        st.session_state[t_key] = 100.0 / float(st.session_state[p_key])

    def _sync_from_p():
        p = float(st.session_state[p_key])
        p = min(max(p, 0.01), 99.99)
        t_val = 100.0 / p
        if t_val <= 1:
            t_val = 1.001
            p = 100.0 / t_val
        elif t_val >= 10000:
            t_val = 9999.0
            p = 100.0 / t_val
        st.session_state[p_key] = p
        st.session_state[t_key] = t_val

    def _sync_from_t():
        t_val = float(st.session_state[t_key])
        t_val = min(max(t_val, 1.001), 9999.999)
        st.session_state[t_key] = t_val
        st.session_state[p_key] = 100.0 / t_val

    col_p, col_t = st.columns(2)
    with col_p:
        st.markdown(t("custom_p_extra"))
        st.number_input(
            t("custom_p_extra"),
            min_value=0.01,
            max_value=99.99,
            format="%.3f",
            key=p_key,
            on_change=_sync_from_p,
            label_visibility="collapsed",
        )
    with col_t:
        st.markdown(t("custom_t_extra"))
        st.number_input(
            t("custom_t_extra"),
            min_value=1.001,
            max_value=9999.999,
            format="%.3f",
            key=t_key,
            on_change=_sync_from_t,
            label_visibility="collapsed",
        )
    return float(st.session_state[p_key])


st.set_page_config(
    page_title=t("page_title"),
    page_icon="📉",
    layout="wide",
    menu_items={"About": t("page_about")},
)

init_language_widgets()

st.title(t("title"))
st.sidebar.markdown(t("sidebar_about"))


def detect_decimal_precision(series, max_reasonable=6):
    """
    Сколько знаков после запятой у исходных данных (минимум 1).
    Игнорирует единичные float-артефакты Excel с длинным хвостом.
    """
    counts = []
    for val in series.dropna():
        try:
            fv = float(val)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(fv) or fv == int(fv):
            continue
        text = np.format_float_positional(fv, trim="-")
        decimals = len(text.split(".")[1]) if "." in text else 0
        counts.append(decimals)

    if not counts:
        return 1
    reasonable = [d for d in counts if d <= max_reasonable]
    if not reasonable:
        return max_reasonable
    return max(reasonable)


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
        if val is None or (isinstance(val, str) and val.strip() == ""):
            return ""
        if isinstance(val, str):
            return val
        try:
            num = float(val)
        except (TypeError, ValueError):
            return str(val)
        if not math.isfinite(num):
            return (
                t("stat_undefined")
                if isinstance(val, (float, np.floating))
                else str(val)
            )
        min_decimals = data_precision if col_idx in data_scale_cols else None
        return str(custom_round(num, min_decimals=min_decimals))

    parts = ["<table>", "<thead><tr>"]
    corner = df.columns.name or df.index.name or t("distribution")
    parts.append(f"<th>{corner}</th>")
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


st.markdown(
    """
    <style>
    /* Все подписи виджетов — как обычный markdown-текст */
    [data-testid="stWidgetLabel"] p {
        font-size: 1rem !important;
        font-weight: 400 !important;
        line-height: 1.6 !important;
    }
    /* Зона upload и кнопка примера — одна высота */
    div[data-testid="stHorizontalBlock"]:has([data-testid="stFileUploader"])
      [data-testid="stFileUploaderDropzone"] {
        min-height: 5rem;
        align-items: center;
    }
    div[data-testid="stHorizontalBlock"]:has([data-testid="stFileUploader"])
      > div:nth-child(2) button {
        min-height: 5rem;
        width: 100%;
    }
    /* Вкладки на всю ширину страницы */
    div[data-testid="stTabs"] [data-baseweb="tab-list"] {
        width: 100%;
        gap: 0.25rem;
    }
    div[data-testid="stTabs"] [data-baseweb="tab"] {
        flex: 1 1 0;
        justify-content: center;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

tab_load, tab_prep, tab_process, tab_results = st.tabs(
    [
        t("tab_load"),
        t("tab_prep"),
        t("tab_process"),
        t("tab_results"),
    ]
)

active_file = None
df = None
prep_ok = False
process_ok = False
series_df = None
data_empirical = None
values_col = None
index_col = None
agg_key = None
precision = 1
results_curve_png = None
results_parameters_df = None
results_quantiles_df = None

with tab_load:
    col_upload, col_sample = st.columns(2)
    with col_upload:
        st.markdown(t("upload_label"))
        uploaded_file = st.file_uploader(
            t("upload_label"),
            type=["xls", "xlsx", "xlsm"],
            label_visibility="collapsed",
            key="excel_upload",
        )
    with col_sample:
        st.markdown(t("sample_label"))
        if st.button(
            t("sample_button"),
            use_container_width=True,
            key="load_sample_btn",
        ):
            if not SAMPLE_DATA_PATH.is_file():
                st.error(t("sample_missing", name=SAMPLE_DATA_PATH.name))
                st.stop()
            st.session_state["use_sample_data"] = True
            st.rerun()

    if uploaded_file is not None:
        st.session_state["use_sample_data"] = False
        active_file = uploaded_file
    elif st.session_state.get("use_sample_data"):
        active_file = load_sample_file()
    else:
        active_file = None

    if active_file:
        try:
            df = read_excel(active_file)
            df = localize_sample_columns(df)
            st.success(
                t(
                    "load_success",
                    n=len(df),
                    rows=pluralize_rows(len(df)),
                )
            )
            log_analytics(uploaded_file=active_file)
            update_analytics_file_rows(len(df))
            with st.expander(t("data_preview"), expanded=False):
                st.markdown(df.head().to_html(), unsafe_allow_html=True)
        except Exception as e:
            st.error(t("error_prefix", error=str(e)))
            df = None
            active_file = None
    else:
        st.info(t("load_hint"))

with tab_prep:
    if df is None:
        st.info(t("prep_need_load"))
    else:
        try:
            numeric_cols = df.select_dtypes(include=["number"]).columns
            cols = df.columns.tolist()
            if len(numeric_cols) == 0:
                st.error(t("no_numeric"))
            else:
                use_sample = bool(st.session_state.get("use_sample_data"))
                values_col = st.selectbox(
                    t("select_values"),
                    numeric_cols,
                    index=option_index(
                        numeric_cols,
                        sample_col(SAMPLE_VALUES_COL) if use_sample else None,
                    ),
                )
                df.rename(columns={values_col: str(values_col)}, inplace=True)

                null_count = df[values_col].isna().sum()
                if null_count > 0:
                    st.markdown(t("nulls_removed"))
                    st.markdown(
                        df[df[values_col].isna()].to_html(),
                        unsafe_allow_html=True,
                    )
                    df = df.dropna(subset=[values_col])

                group_options = [NO_GROUP] + cols
                index_col = st.selectbox(
                    t("select_group"),
                    group_options,
                    index=option_index(
                        group_options,
                        sample_col(SAMPLE_GROUP_COL) if use_sample else NO_GROUP,
                    ),
                    format_func=lambda c: t("no_group") if c == NO_GROUP else c,
                )
                agg_key = None
                if index_col != NO_GROUP:
                    agg_key = st.selectbox(
                        t("select_agg"),
                        AGG_KEYS,
                        index=option_index(
                            AGG_KEYS, SAMPLE_AGG_KEY if use_sample else None
                        ),
                        format_func=lambda k: t(k),
                    )
                    df.rename(columns={index_col: str(index_col)}, inplace=True)

                if index_col != NO_GROUP:
                    series_df = (
                        df.pivot_table(
                            index=index_col,
                            values=values_col,
                            aggfunc=AGG_FUNCS[agg_key],
                        )
                        .reset_index()
                    )
                else:
                    series_df = pd.DataFrame(
                        {values_col: df[values_col].to_numpy(copy=True)}
                    )

                if agg_key == "agg_mean":
                    precision = detect_decimal_precision(df[values_col])
                else:
                    precision = detect_decimal_precision(series_df[values_col])

                exclude_options = []
                exclude_key_to_pos = {}
                for pos in range(len(series_df)):
                    val_txt = custom_round(
                        series_df.iloc[pos][values_col], min_decimals=precision
                    )
                    if index_col != NO_GROUP:
                        label = f"{series_df.iloc[pos][index_col]} - {val_txt}"
                    else:
                        label = str(val_txt)
                    base = label
                    suffix = 2
                    while label in exclude_key_to_pos:
                        label = f"{base} ({suffix})"
                        suffix += 1
                    exclude_key_to_pos[label] = pos
                    exclude_options.append(label)

                excluded_labels = st.multiselect(
                    t("exclude_select"),
                    exclude_options,
                )
                if excluded_labels:
                    drop_positions = {
                        exclude_key_to_pos[label] for label in excluded_labels
                    }
                    series_df = series_df.drop(
                        index=[series_df.index[p] for p in sorted(drop_positions)]
                    ).reset_index(drop=True)

                x_plot = (
                    series_df[index_col]
                    if index_col != NO_GROUP
                    else series_df.index
                )
                with st.expander(t("chart_series"), expanded=False):
                    fig_plotly = go.Figure(
                        data=[
                            go.Scatter(
                                x=list(x_plot),
                                y=series_df[values_col].tolist(),
                                mode="lines+markers",
                                marker={"size": 6},
                                line={"width": 1},
                                name=values_col,
                            )
                        ]
                    )
                    fig_plotly.update_layout(
                        title=t("chart_series_title"),
                        xaxis_title=(
                            index_col if index_col != NO_GROUP else t("axis_index")
                        ),
                        yaxis_title=values_col,
                        height=360,
                        margin={"l": 40, "r": 20, "t": 40, "b": 40},
                    )
                    st.plotly_chart(fig_plotly, use_container_width=True)

                if len(series_df) < 3:
                    st.error(t("too_few_points"))
                else:
                    data = series_df.copy()
                    n = len(data)
                    data["Ранг"] = np.arange(1, n + 1)
                    max_rank_plus_one = n + 1
                    data["Вероятность"] = data["Ранг"] / max_rank_plus_one
                    data["Обеспеченность P, %"] = round(data["Вероятность"] * 100, 2)
                    data_to_merge = data.sort_values(by=values_col, ascending=False)
                    data_to_merge.drop(
                        ["Вероятность", "Обеспеченность P, %", "Ранг"],
                        axis=1,
                        inplace=True,
                    )
                    data_to_merge.rename(
                        columns={values_col: values_col + " (P)"}, inplace=True
                    )
                    if index_col != NO_GROUP:
                        data_to_merge.rename(
                            columns={index_col: index_col + " (P)"}, inplace=True
                        )
                    data_to_merge["Ранг"] = np.arange(1, n + 1)
                    data = data.merge(data_to_merge, on="Ранг")
                    data.set_index("Ранг", inplace=True)
                    data_empirical = data.copy()
                    prep_ok = True
        except Exception as e:
            st.error(t("error_prefix", error=str(e)))
            prep_ok = False

with tab_process:
    if not prep_ok:
        st.info(t("process_need_prep"))
    else:
        try:
            importlib.reload(curve_analysis_mod)
            from curve_analysis import (
                PERCENT_LIST_DEFAULT,
                apply_exceedance_axes,
                build_empirical,
                compound_ppf,
                distribution_moments,
                empirical_column_metrics,
                fig_to_png_bytes,
                fit_quality,
                make_cdf_func,
                teor_x_grid,
            )

            if "curve_mode" not in st.session_state:
                st.session_state.curve_mode = "simple"

            def _set_curve_mode(mode: str):
                st.session_state.curve_mode = mode

            st.markdown(f"**{t('curve_mode')}**")
            col_m1, col_m2, col_m3 = st.columns(3)
            with col_m1:
                st.button(
                    t("curve_mode_simple"),
                    key="curve_mode_btn_simple",
                    use_container_width=True,
                    type=(
                        "primary"
                        if st.session_state.curve_mode == "simple"
                        else "secondary"
                    ),
                    on_click=_set_curve_mode,
                    args=("simple",),
                )
            with col_m2:
                st.button(
                    t("curve_mode_truncated"),
                    key="curve_mode_btn_truncated",
                    use_container_width=True,
                    type=(
                        "primary"
                        if st.session_state.curve_mode == "truncated"
                        else "secondary"
                    ),
                    on_click=_set_curve_mode,
                    args=("truncated",),
                )
            with col_m3:
                st.button(
                    t("curve_mode_compound"),
                    key="curve_mode_btn_compound",
                    use_container_width=True,
                    type=(
                        "primary"
                        if st.session_state.curve_mode == "compound"
                        else "secondary"
                    ),
                    on_click=_set_curve_mode,
                    args=("compound",),
                )
            curve_mode = st.session_state.curve_mode

            work_series = series_df.reset_index(drop=True).copy()
            row_labels, row_label_to_pos = series_row_labels(
                work_series, values_col, index_col, precision
            )

            # --- truncation: reduce work_series, then ordinary analysis ---
            if curve_mode == "truncated":
                trunc_label_to_key = {
                    t("trunc_by_rows"): "by_rows",
                    t("trunc_by_threshold"): "by_threshold",
                }
                if st.session_state.get("ui_trunc_method") not in trunc_label_to_key:
                    st.session_state.pop("ui_trunc_method", None)
                trunc_choice = st.radio(
                    t("trunc_method"),
                    list(trunc_label_to_key.keys()),
                    key="ui_trunc_method",
                )
                trunc_method = trunc_label_to_key.get(trunc_choice, "by_rows")
                n_all = len(work_series)
                if trunc_method == "by_rows":
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.caption(t("trunc_row_first"))
                        first_lab = st.selectbox(
                            t("trunc_row_first"),
                            row_labels,
                            index=0,
                            key="ui_trunc_row_first",
                            label_visibility="collapsed",
                        )
                    with col_b:
                        st.caption(t("trunc_row_last"))
                        last_lab = st.selectbox(
                            t("trunc_row_last"),
                            row_labels,
                            index=max(n_all - 1, 0),
                            key="ui_trunc_row_last",
                            label_visibility="collapsed",
                        )
                    i0 = row_label_to_pos[first_lab]
                    i1 = row_label_to_pos[last_lab]
                    if i0 > i1:
                        st.error(t("trunc_range_invalid"))
                        st.stop()
                    work_series = work_series.iloc[i0 : i1 + 1].reset_index(drop=True)
                else:
                    vmin = float(work_series[values_col].min())
                    vmax = float(work_series[values_col].max())
                    col_lo, col_hi = st.columns(2)
                    with col_lo:
                        st.caption(t("trunc_threshold_lo"))
                        thr_lo = st.number_input(
                            t("trunc_threshold_lo"),
                            value=vmin,
                            key="ui_trunc_thr_lo",
                            label_visibility="collapsed",
                        )
                    with col_hi:
                        st.caption(t("trunc_threshold_hi"))
                        thr_hi = st.number_input(
                            t("trunc_threshold_hi"),
                            value=vmax,
                            key="ui_trunc_thr_hi",
                            label_visibility="collapsed",
                        )
                    lo, hi = min(thr_lo, thr_hi), max(thr_lo, thr_hi)
                    work_series = work_series[
                        (work_series[values_col] >= lo)
                        & (work_series[values_col] <= hi)
                    ].reset_index(drop=True)
                if len(work_series) < 3:
                    st.error(t("too_few_points"))
                    st.stop()
                data_empirical = build_empirical(work_series, values_col, index_col)
                series_df = work_series

            # --- compound: split into two segments ---
            segments = None
            if curve_mode == "compound":
                split_label_to_key = {
                    t("split_from_row"): "from_row",
                    t("split_by_column"): "by_column",
                    t("split_by_threshold"): "by_threshold",
                    t("split_manual"): "manual",
                }
                if st.session_state.get("ui_split_method") not in split_label_to_key:
                    st.session_state.pop("ui_split_method", None)
                split_choice = st.radio(
                    t("split_method"),
                    list(split_label_to_key.keys()),
                    key="ui_split_method",
                )
                split_method = split_label_to_key.get(split_choice, "from_row")
                n_all = len(work_series)
                mask2 = np.zeros(n_all, dtype=bool)

                if split_method == "from_row":
                    default_i = min(max(n_all // 2, 1), n_all - 1)
                    st.caption(t("split_row_start"))
                    start_lab = st.selectbox(
                        t("split_row_start"),
                        row_labels,
                        index=default_i,
                        key="ui_split_row_label",
                        label_visibility="collapsed",
                    )
                    start_pos = row_label_to_pos[start_lab]
                    mask2[start_pos:] = True
                elif split_method == "by_column":
                    crit_candidates = [c for c in df.columns if c != values_col]
                    if not crit_candidates:
                        st.error(t("split_need_criterion"))
                        st.stop()
                    st.caption(t("split_criterion_col"))
                    criterion_col = st.selectbox(
                        t("split_criterion_col"),
                        crit_candidates,
                        key="ui_split_criterion_col",
                        label_visibility="collapsed",
                    )
                    crit_vals = criterion_for_series(
                        work_series,
                        df,
                        values_col,
                        index_col,
                        criterion_col,
                        agg_key,
                    )
                    if crit_vals is None:
                        st.error(t("split_need_criterion"))
                        st.stop()
                    uniq = list(pd.unique(crit_vals))
                    uniq_display = [u for u in uniq if pd.notna(u)]
                    default_seg2 = uniq_display[len(uniq_display) // 2 :]
                    st.caption(t("split_criterion_seg2"))
                    chosen = st.multiselect(
                        t("split_criterion_seg2"),
                        uniq_display,
                        default=default_seg2,
                        key="ui_split_criterion_vals",
                        label_visibility="collapsed",
                    )
                    mask2 = pd.Series(crit_vals).isin(chosen).to_numpy()
                elif split_method == "by_threshold":
                    st.caption(t("split_value_threshold"))
                    thr = st.number_input(
                        t("split_value_threshold"),
                        value=float(work_series[values_col].median()),
                        key="ui_split_val_thr",
                        label_visibility="collapsed",
                    )
                    mask2 = (work_series[values_col] >= thr).to_numpy()
                else:
                    st.caption(t("split_manual_seg2"))
                    chosen = st.multiselect(
                        t("split_manual_seg2"),
                        row_labels,
                        key="ui_split_manual_pts",
                        label_visibility="collapsed",
                    )
                    for lab in chosen:
                        mask2[row_label_to_pos[lab]] = True

                seg1 = work_series.loc[~mask2].reset_index(drop=True)
                seg2 = work_series.loc[mask2].reset_index(drop=True)

                # preview on time chart
                with st.expander(t("split_preview"), expanded=True):
                    fig_p, ax_p = plt.subplots(figsize=(12, 4))
                    x_all = (
                        work_series[index_col]
                        if index_col != NO_GROUP
                        else work_series.index
                    )
                    ax_p.plot(
                        x_all[~mask2],
                        work_series.loc[~mask2, values_col],
                        "o-",
                        color="#1f77b4",
                        label=t("segment_title", i=1, n=len(seg1)),
                    )
                    ax_p.plot(
                        x_all[mask2],
                        work_series.loc[mask2, values_col],
                        "o-",
                        color="#ff7f0e",
                        label=t("segment_title", i=2, n=len(seg2)),
                    )
                    ax_p.set_ylabel(values_col)
                    ax_p.legend()
                    st.pyplot(fig_p, width="content")
                    plt.close(fig_p)

                if len(seg1) < 3:
                    st.error(t("segment_too_small", i=1))
                    st.stop()
                if len(seg2) < 3:
                    st.error(t("segment_too_small", i=2))
                    st.stop()
                segments = [seg1, seg2]
                data_empirical = build_empirical(work_series, values_col, index_col)

            # ========== ORDINARY / TRUNCATED path ==========
            if curve_mode in ("simple", "truncated"):
                data = data_empirical.sort_values(by=values_col)
                data_min = data[values_col].min()
                data_max = data[values_col].max()
                distributions = build_distributions(data_min, data_max)

                import html as _html

                tip = _html.escape(t("dist_tooltip")).replace("\n", "&#10;")
                st.markdown(
                    f'{t("select_dist")} '
                    f'<span title="{tip}" style="cursor:help;color:#666;">ⓘ</span>',
                    unsafe_allow_html=True,
                )
                distributions_to_plot = st.multiselect(
                    t("select_dist"),
                    list(distributions.keys()),
                    default=[list(distributions)[-1]],
                    format_func=dist_label,
                    label_visibility="collapsed",
                )
                if distributions_to_plot:
                    log_analytics(
                        uploaded_file=active_file,
                        distributions_selected=distributions_to_plot,
                    )

                fig, ax = plt.subplots(figsize=(12, 6))
                x = data["Вероятность"] * 100
                y = data[values_col + " (P)"]
                ax.scatter(
                    x,
                    y,
                    label=t("empirical"),
                    s=36,
                    facecolors="none",
                    edgecolors="black",
                    linewidths=1.2,
                )

                file_key = getattr(active_file, "name", None)
                if st.session_state.get("_ensurance_file_key") != file_key:
                    st.session_state.added_ensurance_values = []
                    st.session_state["_ensurance_file_key"] = file_key
                added_p = list(st.session_state.get("added_ensurance_values", []))
                all_percents = sorted(set(PERCENT_LIST_DEFAULT) | set(added_p))
                df_1 = pd.DataFrame(all_percents, columns=["Обеспеченность"])

                parameters = ["Среднее", "Cv", "Cs", "R²", "MAE", "maxE", "A-D"]
                parameters_df = pd.DataFrame(parameters, columns=["Распределение"])
                mean, cv, cs = empirical_column_metrics(data, values_col)
                parameters_df["Эмпирическое"] = pd.DataFrame(
                    [mean, cv, cs, "-", "-", "-", "-"]
                )

                distribution_params = {}
                x_teor = teor_x_grid()

                for distribution in distributions_to_plot:
                    selected_dist = distributions[distribution]
                    params = selected_dist.fit(data[values_col])
                    distribution_params[distribution] = params
                    r2, mae, maxE, ad_stat = fit_quality(
                        data, values_col, selected_dist, params
                    )
                    mean_d, cv_d, cs_d = distribution_moments(
                        selected_dist, params, distribution
                    )
                    y_teor = np.vectorize(
                        lambda xx, dist=selected_dist, p=params: dist.ppf(
                            1 - xx / 100, *p
                        )
                    )(x_teor)
                    ax.plot(
                        x_teor,
                        y_teor,
                        label=dist_label(distribution),
                        linewidth=1.8,
                    )
                    df_1[distribution] = df_1["Обеспеченность"].apply(
                        lambda xx, dist=selected_dist, p=params: custom_round(
                            dist.ppf(1 - xx / 100, *p), min_decimals=precision
                        )
                    )
                    parameters_df[distribution] = pd.DataFrame(
                        [mean_d, cv_d, cs_d, r2, mae, maxE, ad_stat]
                    )

                apply_exceedance_axes(ax, values_col)
                ax.legend(title=t("legend_dist"), fontsize=11, title_fontsize=12)
                st.pyplot(fig, width="content")
                results_curve_png = fig_to_png_bytes(fig)

                parameters_df_view = localize_parameters_view(
                    parameters_df.set_index("Распределение", drop=True).T
                )
                quantiles_df_view = localize_quantiles_view(
                    with_return_period_row(df_1).T.copy()
                )

                with st.expander(t("metrics_expander"), expanded=False):
                    st.markdown(
                        style_dataframe_html(
                            parameters_df_view, data_precision=precision
                        ),
                        unsafe_allow_html=True,
                    )
                    if len(parameters_df_view) >= 2:
                        st.markdown(t("metrics_note"), unsafe_allow_html=True)
                    st.markdown(t("metrics_legend"), unsafe_allow_html=True)

                with st.expander(t("quantiles_expander"), expanded=False):
                    st.markdown(
                        quantiles_df_view.to_html(index=True, header=False),
                        unsafe_allow_html=True,
                    )
                    p = linked_exceedance_inputs("custom_simple", default_p=20.0)
                    if (
                        "last_logged_p" not in st.session_state
                        or st.session_state.last_logged_p != p
                    ):
                        log_analytics(
                            uploaded_file=active_file,
                            distributions_selected=distributions_to_plot,
                            custom_ensurence_value=p,
                        )
                        st.session_state.last_logged_p = p
                    if distributions_to_plot:
                        custom_dict = {
                            dist_label(d): custom_round(
                                distributions[d].ppf(
                                    1 - p / 100, *distribution_params[d]
                                ),
                                min_decimals=precision,
                            )
                            for d in distributions_to_plot
                        }
                        custom_df = pd.DataFrame.from_dict(
                            custom_dict, orient="index", columns=["Values"]
                        )
                        col_add_tbl, col_add_btn, _ = st.columns([1.4, 1, 3.5])
                        with col_add_tbl:
                            st.markdown(
                                custom_df.to_html(index=True, header=False),
                                unsafe_allow_html=True,
                            )
                        with col_add_btn:
                            if st.button(
                                t("add_to_table"),
                                use_container_width=True,
                                key="add_p_simple",
                            ):
                                if any(
                                    abs(float(p) - float(e)) < 1e-9
                                    for e in all_percents
                                ):
                                    st.info(t("p_already"))
                                else:
                                    st.session_state.added_ensurance_values = (
                                        added_p + [float(p)]
                                    )
                                    st.rerun()

                results_parameters_df = parameters_df_view
                results_quantiles_df = quantiles_df_view
                process_ok = True

            # ========== COMPOUND path ==========
            elif curve_mode == "compound" and segments is not None:
                import html as _html

                tip = _html.escape(t("dist_tooltip")).replace("\n", "&#10;")
                segment_fits = []

                for i, seg in enumerate(segments, start=1):
                    st.subheader(t("segment_title", i=i, n=len(seg)))
                    emp_i = build_empirical(seg, values_col, index_col)
                    data_i = emp_i.sort_values(by=values_col)
                    distributions_i = build_distributions(
                        data_i[values_col].min(), data_i[values_col].max()
                    )
                    st.markdown(
                        f'{t("select_dist_one")} '
                        f'<span title="{tip}" style="cursor:help;color:#666;">ⓘ</span>',
                        unsafe_allow_html=True,
                    )
                    dist_name = st.selectbox(
                        t("select_dist_one"),
                        list(distributions_i.keys()),
                        index=len(distributions_i) - 1,
                        format_func=dist_label,
                        key=f"seg_dist_{i}",
                        label_visibility="collapsed",
                    )
                    if not dist_name:
                        st.warning(t("need_one_dist"))
                        st.stop()
                    selected_dist = distributions_i[dist_name]
                    params = selected_dist.fit(data_i[values_col])
                    log_analytics(
                        uploaded_file=active_file,
                        distributions_selected=[dist_name],
                    )

                    fig_i, ax_i = plt.subplots(figsize=(12, 6))
                    ax_i.scatter(
                        data_i["Вероятность"] * 100,
                        data_i[values_col + " (P)"],
                        label=t("empirical"),
                        s=36,
                        facecolors="none",
                        edgecolors="black",
                        linewidths=1.2,
                    )
                    x_teor = teor_x_grid()
                    y_teor = np.vectorize(
                        lambda xx, dist=selected_dist, p=params: dist.ppf(
                            1 - xx / 100, *p
                        )
                    )(x_teor)
                    ax_i.plot(
                        x_teor,
                        y_teor,
                        label=dist_label(dist_name),
                        linewidth=1.8,
                    )
                    apply_exceedance_axes(ax_i, values_col)
                    ax_i.legend(title=t("legend_dist"), fontsize=11, title_fontsize=12)
                    st.pyplot(fig_i, width="content")
                    plt.close(fig_i)

                    r2, mae, maxE, ad_stat = fit_quality(
                        data_i, values_col, selected_dist, params
                    )
                    mean_d, cv_d, cs_d = distribution_moments(
                        selected_dist, params, dist_name
                    )
                    mean_e, cv_e, cs_e = empirical_column_metrics(data_i, values_col)
                    parameters_df = pd.DataFrame(
                        {
                            "Распределение": [
                                "Среднее",
                                "Cv",
                                "Cs",
                                "R²",
                                "MAE",
                                "maxE",
                                "A-D",
                            ],
                            "Эмпирическое": [
                                mean_e,
                                cv_e,
                                cs_e,
                                "-",
                                "-",
                                "-",
                                "-",
                            ],
                            dist_name: [
                                mean_d,
                                cv_d,
                                cs_d,
                                r2,
                                mae,
                                maxE,
                                ad_stat,
                            ],
                        }
                    )
                    parameters_df_view = localize_parameters_view(
                        parameters_df.set_index("Распределение", drop=True).T
                    )
                    with st.expander(t("metrics_expander"), expanded=False):
                        st.markdown(
                            style_dataframe_html(
                                parameters_df_view, data_precision=precision
                            ),
                            unsafe_allow_html=True,
                        )
                        st.markdown(t("metrics_legend"), unsafe_allow_html=True)

                    segment_fits.append(
                        {
                            "name": dist_name,
                            "dist": selected_dist,
                            "params": params,
                            "n": len(seg),
                            "cdf": make_cdf_func(selected_dist, params, dist_name),
                            "data": data_i,
                            "metrics_view": parameters_df_view,
                        }
                    )

                # --- compound curve ---
                st.subheader(t("compound_curve_title"))
                data_full = data_empirical.sort_values(by=values_col)
                cdf_funcs = [f["cdf"] for f in segment_fits]
                ns = [f["n"] for f in segment_fits]

                fig_c, ax_c = plt.subplots(figsize=(12, 6))
                y_emp = data_full[values_col + " (P)"].to_numpy(dtype=float)
                ax_c.scatter(
                    data_full["Вероятность"] * 100,
                    y_emp,
                    label=t("empirical"),
                    s=36,
                    facecolors="none",
                    edgecolors="black",
                    linewidths=1.2,
                )

                # bounds for root-finding: around data, with mild tail margin
                data_min = float(np.nanmin(y_emp))
                data_max = float(np.nanmax(y_emp))
                span = max(data_max - data_min, abs(data_max), abs(data_min), 1.0)
                x_lo, x_hi = data_min - 0.5 * span, data_max + 0.5 * span
                for f in segment_fits:
                    try:
                        x_hi = max(
                            x_hi,
                            float(f["dist"].ppf(1 - 0.1 / 100, *f["params"])),
                        )
                        x_lo = min(
                            x_lo,
                            float(f["dist"].ppf(1 - 99.9 / 100, *f["params"])),
                        )
                    except Exception:
                        pass

                # same probability grid as ordinary curves → no empty vertical space
                x_teor = teor_x_grid()
                y_teor = np.array(
                    [
                        compound_ppf(float(p), cdf_funcs, ns, x_lo, x_hi)
                        for p in x_teor
                    ],
                    dtype=float,
                )
                valid = np.isfinite(y_teor)
                ax_c.plot(
                    x_teor[valid],
                    y_teor[valid],
                    linewidth=1.8,
                    label=t("compound_label"),
                )
                apply_exceedance_axes(ax_c, values_col, title=t("compound_curve_title"))
                ys = np.concatenate([y_emp[np.isfinite(y_emp)], y_teor[valid]])
                if len(ys):
                    y0, y1 = float(np.min(ys)), float(np.max(ys))
                    pad = 0.05 * max(y1 - y0, 1e-9)
                    ax_c.set_ylim(y0 - pad, y1 + pad)
                ax_c.legend(title=t("legend_dist"), fontsize=11, title_fontsize=12)
                st.pyplot(fig_c, width="content")
                results_curve_png = fig_to_png_bytes(fig_c)

                # compound metrics vs empirical full series
                predict_c = []
                for _, row in data_full.iterrows():
                    p_emp = float(row["Вероятность"] * 100)
                    predict_c.append(
                        compound_ppf(p_emp, cdf_funcs, ns, x_lo, x_hi)
                    )
                predict_c = np.asarray(predict_c, dtype=float)
                y_emp = data_full[values_col + " (P)"].to_numpy(dtype=float)
                valid = np.isfinite(predict_c)
                if valid.sum() >= 3:
                    r2 = r2_score(y_emp[valid], predict_c[valid])
                    mae = mean_absolute_error(y_emp[valid], predict_c[valid])
                    maxE = max_error(y_emp[valid], predict_c[valid])
                else:
                    r2 = mae = maxE = np.nan
                mean_e, cv_e, cs_e = empirical_column_metrics(data_full, values_col)
                # moments for compound: weighted means of component moments
                means = []
                for f in segment_fits:
                    m, _, _ = distribution_moments(f["dist"], f["params"], f["name"])
                    means.append(m if not isinstance(m, str) else np.nan)
                try:
                    mean_c = float(np.nansum([m * n for m, n in zip(means, ns)]) / sum(ns))
                except Exception:
                    mean_c = t("error_label")
                parameters_df = pd.DataFrame(
                    {
                        "Распределение": [
                            "Среднее",
                            "Cv",
                            "Cs",
                            "R²",
                            "MAE",
                            "maxE",
                            "A-D",
                        ],
                        "Эмпирическое": [mean_e, cv_e, cs_e, "-", "-", "-", "-"],
                        t("compound_label"): [
                            mean_c,
                            "-",
                            "-",
                            r2,
                            mae,
                            maxE,
                            "-",
                        ],
                    }
                )
                parameters_df_view = localize_parameters_view(
                    parameters_df.set_index("Распределение", drop=True).T
                )
                with st.expander(t("compound_metrics"), expanded=False):
                    st.markdown(
                        style_dataframe_html(
                            parameters_df_view, data_precision=precision
                        ),
                        unsafe_allow_html=True,
                    )
                    st.markdown(t("metrics_legend"), unsafe_allow_html=True)

                file_key = getattr(active_file, "name", None)
                if st.session_state.get("_ensurance_file_key") != file_key:
                    st.session_state.added_ensurance_values = []
                    st.session_state["_ensurance_file_key"] = file_key
                added_p = list(st.session_state.get("added_ensurance_values", []))
                all_percents = sorted(set(PERCENT_LIST_DEFAULT) | set(added_p))
                rows = {"Обеспеченность": all_percents}
                compound_vals = []
                for pp in all_percents:
                    q = compound_ppf(pp, cdf_funcs, ns, x_lo, x_hi)
                    compound_vals.append(
                        custom_round(q, min_decimals=precision)
                        if np.isfinite(q)
                        else "—"
                    )
                rows[t("compound_label")] = compound_vals
                df_1 = pd.DataFrame(rows)
                quantiles_df_view = localize_quantiles_view(
                    with_return_period_row(df_1).T.copy()
                )

                with st.expander(t("quantiles_expander"), expanded=False):
                    st.markdown(
                        quantiles_df_view.to_html(index=True, header=False),
                        unsafe_allow_html=True,
                    )
                    p = linked_exceedance_inputs("custom_compound", default_p=20.0)
                    val = compound_ppf(p, cdf_funcs, ns, x_lo, x_hi)
                    custom_df = pd.DataFrame(
                        {
                            "Values": [
                                custom_round(val, min_decimals=precision)
                                if np.isfinite(val)
                                else "—"
                            ]
                        },
                        index=[t("compound_label")],
                    )
                    col_add_tbl, col_add_btn, _ = st.columns([1.4, 1, 3.5])
                    with col_add_tbl:
                        st.markdown(
                            custom_df.to_html(index=True, header=False),
                            unsafe_allow_html=True,
                        )
                    with col_add_btn:
                        if st.button(
                            t("add_to_table"),
                            use_container_width=True,
                            key="add_p_compound",
                        ):
                            if any(
                                abs(float(p) - float(e)) < 1e-9 for e in all_percents
                            ):
                                st.info(t("p_already"))
                            else:
                                st.session_state.added_ensurance_values = added_p + [
                                    float(p)
                                ]
                                st.rerun()

                results_parameters_df = parameters_df_view
                results_quantiles_df = quantiles_df_view
                process_ok = True

        except Exception as e:
            st.error(t("error_prefix", error=str(e)))

with tab_results:
    if not prep_ok:
        st.info(t("results_need_prep"))
    else:
        try:
            with st.expander(t("empirical_expander"), expanded=False):
                display_emp = data_empirical.copy()
                display_emp = display_emp.rename(
                    columns={"Обеспеченность P, %": t("ensurance_p_pct")}
                )
                if index_col != NO_GROUP:
                    st.markdown(
                        display_emp[
                            [
                                index_col,
                                values_col,
                                t("ensurance_p_pct"),
                                values_col + " (P)",
                                index_col + " (P)",
                            ]
                        ].to_html(),
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        display_emp[
                            [
                                values_col,
                                t("ensurance_p_pct"),
                                values_col + " (P)",
                            ]
                        ].to_html(),
                        unsafe_allow_html=True,
                    )

            with st.expander(t("chart_series"), expanded=False):
                fig, ax = plt.subplots(figsize=(12, 6))
                x = (
                    series_df[index_col]
                    if index_col != NO_GROUP
                    else series_df.index
                )
                y = series_df[values_col]
                plt.plot(x, y, linewidth=1.5)
                ax.set_ylabel(values_col, fontsize=12)
                ax.set_title(t("chart_series_title"), fontsize=14)
                ax.tick_params(axis="x", labelsize=11)
                ax.tick_params(axis="y", labelsize=11)
                if index_col != NO_GROUP:
                    ax.set_xlabel(index_col, fontsize=12)
                st.pyplot(fig, width="content")
                plt.close(fig)

            if process_ok and results_curve_png is not None:
                with st.expander(t("curves_expander"), expanded=False):
                    st.image(results_curve_png, use_container_width=True)

            if process_ok and results_parameters_df is not None:
                with st.expander(t("metrics_expander"), expanded=False):
                    st.markdown(
                        style_dataframe_html(
                            results_parameters_df, data_precision=precision
                        ),
                        unsafe_allow_html=True,
                    )

            if process_ok and results_quantiles_df is not None:
                with st.expander(t("quantiles_expander"), expanded=False):
                    st.markdown(
                        results_quantiles_df.to_html(index=True, header=False),
                        unsafe_allow_html=True,
                    )

            docx_bytes = build_results_docx(
                series_df=series_df,
                data=data_empirical,
                values_col=values_col,
                index_col=index_col,
                curve_png=results_curve_png,
                parameters_df=results_parameters_df,
                quantiles_df=results_quantiles_df,
                data_precision=precision,
                lang=st.session_state.get("lang", "ru"),
                no_group_marker=NO_GROUP,
            )
            st.download_button(
                t("download_results"),
                data=docx_bytes,
                file_name=t("docx_filename"),
                mime=(
                    "application/vnd.openxmlformats-officedocument"
                    ".wordprocessingml.document"
                ),
                use_container_width=True,
            )
        except Exception as e:
            st.error(t("error_prefix", error=str(e)))
