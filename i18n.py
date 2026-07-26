"""Локализация UI: русский / английский."""

from __future__ import annotations

TRANSLATIONS = {
    "ru": {
        "page_title": "Кривые обеспеченности",
        "page_about": "Приложение для анализа экстремальных событий",
        "title": "📉 Кривые обеспеченности",
        "lang_section_radio": "Язык",
        "lang_section_buttons": "Язык",
        "lang_ru": "Русский",
        "lang_en": "English",
        "sidebar_about": """### ℹ️ О проекте
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

🙏 Спасибо за поддержку: Мише Самохину, Никите З., Татьяне Д., Елене Л., Марине М., Валентину Марченко, Татьяне Ш., Алмазу Х., Сергею, Ивану К., Евгению К., Константину Д., Дмитрию К.""",
        "tab_load": "Загрузка данных",
        "tab_prep": "Подготовка данных",
        "tab_process": "Обработка данных",
        "tab_results": "Вывод результатов",
        "upload_label": "Загрузите Excel файл",
        "sample_label": "Или воспользуйтесь примером",
        "sample_button": "Загрузить тестовый файл",
        "sample_missing": "Тестовый файл не найден: {name}",
        "load_success": "Данные успешно загружены и содержат {n} {rows}",
        "rows_1": "строку",
        "rows_2": "строки",
        "rows_5": "строк",
        "data_preview": "🔢 Фрагмент загруженных данных",
        "error_prefix": "Ошибка: {error}",
        "load_hint": "Загрузите Excel-файл или тестовый пример, чтобы продолжить.",
        "prep_need_load": "Сначала загрузите данные во вкладке «Загрузка данных».",
        "process_need_prep": "Сначала подготовьте данные во вкладке «Подготовка данных».",
        "results_need_prep": "Сначала подготовьте данные во вкладке «Подготовка данных».",
        "no_numeric": "В файле нет числовых столбцов",
        "select_values": "Выберите столбец с данными для построения кривой обеспеченности",
        "nulls_removed": "В данных обнаружены и удалены для работы пропуски в следующих строках:",
        "select_group": "Выберите столбец для группировки данных",
        "select_agg": "Выберите способ группировки данных",
        "no_group": "Без группировки",
        "agg_max": "Максимальные значения",
        "agg_min": "Минимальные значения",
        "agg_mean": "Средние значения",
        "agg_sum": "Суммарные значения",
        "exclude_select": "Выберите данные для исключения из дальнейшего расчета",
        "chart_series": "📊 График хода значений",
        "chart_series_title": "График хода значений",
        "axis_index": "Индекс",
        "too_few_points": "После исключения осталось слишком мало данных для расчета (нужно не менее 3 значений).",
        "select_dist": "Выберите распределение для аппроксимации",
        "select_dist_one": "Выберите одно распределение для аппроксимации",
        "dist_tooltip": (
            "Расшифровка аббревиатур:\n"
            "• ММП — метод максимального правдоподобия\n"
            "• Мом — метод моментов\n"
            "• L-мом — метод L-моментов"
        ),
        "curve_mode": "Тип кривой обеспеченности",
        "curve_mode_simple": "Обычная",
        "curve_mode_truncated": "Усечённая",
        "curve_mode_compound": "Составная",
        "split_method": "Как разделить ряд на части",
        "split_from_row": "По строке ряда",
        "split_by_column": "По столбцу",
        "split_by_threshold": "По порогу",
        "split_manual": "Вручную",
        "split_row_start": "Первая строка второй части",
        "split_criterion_col": "Столбец с критерием",
        "split_criterion_seg2": "Значения критерия для второй части",
        "split_value_threshold": "Пороговое значение",
        "split_manual_seg2": "Точки второй части ряда",
        "split_need_criterion": "В данных нет подходящего столбца для критерия.",
        "trunc_method": "Как усечь ряд",
        "trunc_by_rows": "По членам ряда",
        "trunc_by_threshold": "По границам значений",
        "trunc_row_first": "Первый член ряда",
        "trunc_row_last": "Последний член ряда",
        "trunc_threshold_lo": "Нижняя граница",
        "trunc_threshold_hi": "Верхняя граница",
        "segment_title": "Часть {i} ряда (n = {n})",
        "segment_too_small": "В части {i} слишком мало точек (нужно ≥ 3).",
        "compound_curve_title": "Составная кривая обеспеченности",
        "compound_label": "Составное",
        "compound_metrics": "📋 Метрики составной кривой",
        "need_one_dist": "Выберите распределение.",
        "split_preview": "Разделение ряда на графике хода",
        "trunc_range_invalid": "Первая строка должна быть не позже последней.",
        "empirical": "Эмпирическое",
        "ensurance": "Обеспеченность",
        "ensurance_pct": "Обеспеченность, %",
        "return_period_years": "Период повторяемости, годы",
        "return_period": "Период повторяемости",
        "ensurance_p_pct": "Обеспеченность P, %",
        "rank": "Ранг",
        "probability": "Вероятность",
        "distribution": "Распределение",
        "mean": "Среднее",
        "curve_title": "Значения с разной долей обеспеченности",
        "legend_dist": "Вид распределения",
        "metrics_expander": "📋 Параметры и метрики качества полученных распределений",
        "metrics_note": """<b>Примечания к таблице:</b>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;Зелёным цветом показаны значения, ближайшие к эмпирическим, красным - самые удалённые.""",
        "metrics_legend": """<b>Расшифровка названий столбцов:</b>
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
&nbsp;&nbsp;&nbsp;&nbsp;• <b>A-D</b> - Критерий согласия Андерсона-Дарлинга (чем меньше, тем лучше соответствие распределения данным)""",
        "quantiles_expander": "📋 Расчет значений с разной долей обеспеченности (в %)",
        "custom_p_input": "Выберите обеспеченность для расчета значения (0 < P < 100)",
        "custom_p_extra": "Выберите доп. обеспеченность (0 < P < 100)",
        "custom_t_extra": "Или период повторяемости (1 < T < 10 000)",
        "add_to_table": "Добавить в таблицу",
        "need_dist": "Сначала выберите хотя бы одно распределение.",
        "p_already": "Это значение обеспеченности уже есть в таблице.",
        "empirical_expander": "🔢 Хронологический ряд значений и эмпирическое распределение",
        "curves_expander": "📉 Кривые обеспеченности",
        "download_results": "Скачать результаты одним файлом",
        "docx_filename": "результаты_кривые_обеспеченности.docx",
        "docx_title": "Кривые обеспеченности — результаты",
        "docx_empirical": "Эмпирический ряд",
        "docx_series_chart": "График хода значений",
        "docx_curves": "Кривые обеспеченности",
        "docx_metrics": "Параметры и метрики качества полученных распределений",
        "docx_quantiles": "Расчет значений с разной долей обеспеченности (в %)",
        "ad_fail": "Не удалось рассчитать A-D статистику для {name}: {error}",
        "stats_fail": "Ошибка при расчете статистик для {name}: {error}",
        "error_label": "Ошибка",
        "stat_undefined": "Не существует",
        "dist.Гумбеля (ММП)": "Гумбеля (ММП)",
        "dist.Пирсона 3 типа (ММП)": "Пирсона 3 типа (ММП)",
        "dist.Обобщенное (ММП)": "Обобщенное (ММП)",
        "dist.Крицкого-Менкеля (ММП)": "Крицкого-Менкеля (ММП)",
        "dist.Гумбеля (Мом)": "Гумбеля (Мом)",
        "dist.Гумбеля (L-мом)": "Гумбеля (L-мом)",
        "dist.Пирсона 3 типа (L-мом)": "Пирсона 3 типа (L-мом)",
        "dist.Обобщенное (L-мом)": "Обобщенное (L-мом)",
    },
    "en": {
        "page_title": "Exceedance curves",
        "page_about": "App for extreme-value analysis",
        "title": "📉 Exceedance curves",
        "lang_section_radio": "Language",
        "lang_section_buttons": "Language",
        "lang_ru": "Русский",
        "lang_en": "English",
        "sidebar_about": """### ℹ️ About the project
The app automatically builds exceedance (security) curves from raw data.

Ask questions, share ideas, and follow hydrometeorology updates in [our channel](https://t.me/+g8Kjj2t8hvsxYmJi).

We also calculate climate parameters from your data or from a database of 600+ weather stations:
- Air and soil temperature
- Precipitation
- Air humidity
- Snow cover
- Atmospheric phenomena
- Wind characteristics
- Hazardous weather events
- Snow transport
- Evaporation from water surface

Details: [Arseniy Kamyshev](https://t.me/Arseniikamyshev), [Ilia Kurdukov](https://t.me/ilia_kurdukov)


This is a non-commercial project — we appreciate [your support](https://tbank.ru/cf/2PlIaU81b0F) 🍩

🙏 Thanks for support: Misha Samokhin, Nikita Z., Tatiana D., Elena L., Marina M., Valentin Marchenko, Tatiana Sh., Almaz Kh., Sergey, Ivan K., Evgeny K., Konstantin D., Dmitry K.""",
        "tab_load": "Data upload",
        "tab_prep": "Data preparation",
        "tab_process": "Data processing",
        "tab_results": "Results",
        "upload_label": "Upload an Excel file",
        "sample_label": "Or use a sample",
        "sample_button": "Load sample file",
        "sample_missing": "Sample file not found: {name}",
        "load_success": "Data loaded successfully: {n} {rows}",
        "rows_1": "row",
        "rows_2": "rows",
        "rows_5": "rows",
        "data_preview": "🔢 Data preview",
        "error_prefix": "Error: {error}",
        "load_hint": "Upload an Excel file or the sample to continue.",
        "prep_need_load": "First upload data in the «Data upload» tab.",
        "process_need_prep": "First prepare data in the «Data preparation» tab.",
        "results_need_prep": "First prepare data in the «Data preparation» tab.",
        "no_numeric": "The file has no numeric columns",
        "select_values": "Select the value column for the exceedance curve",
        "nulls_removed": "Missing values were found and removed from these rows:",
        "select_group": "Select a column for grouping",
        "select_agg": "Select an aggregation method",
        "no_group": "No grouping",
        "agg_max": "Maximum values",
        "agg_min": "Minimum values",
        "agg_mean": "Mean values",
        "agg_sum": "Sum values",
        "exclude_select": "Select points to exclude from further calculation",
        "chart_series": "📊 Time series chart",
        "chart_series_title": "Time series chart",
        "axis_index": "Index",
        "too_few_points": "Too few points left after exclusion (at least 3 required).",
        "select_dist": "Select distributions for fitting",
        "select_dist_one": "Select one distribution for fitting",
        "dist_tooltip": (
            "Abbreviation key:\n"
            "• MLE — maximum likelihood estimation\n"
            "• MoM — method of moments\n"
            "• L-mom — L-moments method"
        ),
        "curve_mode": "Exceedance curve type",
        "curve_mode_simple": "Ordinary",
        "curve_mode_truncated": "Truncated",
        "curve_mode_compound": "Compound",
        "split_method": "How to split the series",
        "split_from_row": "By series row",
        "split_by_column": "By column",
        "split_by_threshold": "By threshold",
        "split_manual": "Manually",
        "split_row_start": "First row of segment 2",
        "split_criterion_col": "Criterion column",
        "split_criterion_seg2": "Criterion values for segment 2",
        "split_value_threshold": "Threshold value",
        "split_manual_seg2": "Points of segment 2",
        "split_need_criterion": "No suitable criterion column in the data.",
        "trunc_method": "How to truncate the series",
        "trunc_by_rows": "By series members",
        "trunc_by_threshold": "By value bounds",
        "trunc_row_first": "First series member",
        "trunc_row_last": "Last series member",
        "trunc_threshold_lo": "Lower bound",
        "trunc_threshold_hi": "Upper bound",
        "segment_title": "Segment {i} (n = {n})",
        "segment_too_small": "Segment {i} has too few points (need ≥ 3).",
        "compound_curve_title": "Compound exceedance curve",
        "compound_label": "Compound",
        "compound_metrics": "📋 Compound curve metrics",
        "need_one_dist": "Select a distribution.",
        "split_preview": "Series split on the time chart",
        "trunc_range_invalid": "The first row must not be after the last row.",
        "empirical": "Empirical",
        "ensurance": "Exceedance",
        "ensurance_pct": "Exceedance, %",
        "return_period_years": "Return period, years",
        "return_period": "Return period",
        "ensurance_p_pct": "Exceedance P, %",
        "rank": "Rank",
        "probability": "Probability",
        "distribution": "Distribution",
        "mean": "Mean",
        "curve_title": "Values at different exceedance levels",
        "legend_dist": "Distribution",
        "metrics_expander": "📋 Distribution parameters and goodness-of-fit metrics",
        "metrics_note": """<b>Table notes:</b>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;Green marks values closest to the empirical ones; red marks the farthest.""",
        "metrics_legend": """<b>Column key:</b>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;• <b>Mean</b> - mean value
<br>
&nbsp;&nbsp;&nbsp;&nbsp;• <b>Cv</b> - coefficient of variation
<br>
&nbsp;&nbsp;&nbsp;&nbsp;• <b>Cs</b> - skewness coefficient
<br>
&nbsp;&nbsp;&nbsp;&nbsp;• <b>R²</b> - coefficient of determination (closer to 1 is better)
<br>
&nbsp;&nbsp;&nbsp;&nbsp;• <b>MAE</b> - mean absolute error
<br>
&nbsp;&nbsp;&nbsp;&nbsp;• <b>maxE</b> - maximum absolute error
<br>
&nbsp;&nbsp;&nbsp;&nbsp;• <b>A-D</b> - Anderson–Darling statistic (smaller is better)""",
        "quantiles_expander": "📋 Values at different exceedance probabilities (%)",
        "custom_p_input": "Choose an exceedance probability to compute (0 < P < 100)",
        "custom_p_extra": "Additional exceedance (0 < P < 100)",
        "custom_t_extra": "Or return period (1 < T < 10,000)",
        "add_to_table": "Add to table",
        "need_dist": "Select at least one distribution first.",
        "p_already": "This exceedance value is already in the table.",
        "empirical_expander": "🔢 Chronological series and empirical distribution",
        "curves_expander": "📉 Exceedance curves",
        "download_results": "Download all results as one file",
        "docx_filename": "exceedance_curves_results.docx",
        "docx_title": "Exceedance curves — results",
        "docx_empirical": "Empirical series",
        "docx_series_chart": "Time series chart",
        "docx_curves": "Exceedance curves",
        "docx_metrics": "Distribution parameters and goodness-of-fit metrics",
        "docx_quantiles": "Values at different exceedance probabilities (%)",
        "ad_fail": "Could not compute A-D statistic for {name}: {error}",
        "stats_fail": "Could not compute statistics for {name}: {error}",
        "error_label": "Error",
        "stat_undefined": "Undefined",
        "dist.Гумбеля (ММП)": "Gumbel (MLE)",
        "dist.Пирсона 3 типа (ММП)": "Pearson type III (MLE)",
        "dist.Обобщенное (ММП)": "GEV (MLE)",
        "dist.Крицкого-Менкеля (ММП)": "Krytsky–Menkel (MLE)",
        "dist.Гумбеля (Мом)": "Gumbel (MoM)",
        "dist.Гумбеля (L-мом)": "Gumbel (L-moments)",
        "dist.Пирсона 3 типа (L-мом)": "Pearson type III (L-moments)",
        "dist.Обобщенное (L-мом)": "GEV (L-moments)",
    },
}

# Внутренние ключи агрегации (не зависят от языка UI)
AGG_KEYS = ["agg_max", "agg_min", "agg_mean", "agg_sum"]
AGG_FUNCS_BY_KEY = {
    "agg_max": "max",
    "agg_min": "min",
    "agg_mean": "mean",
    "agg_sum": "sum",
}
NO_GROUP_KEY = "no_group"


def get_lang() -> str:
    try:
        import streamlit as st

        lang = st.session_state.get("lang", "ru")
        return lang if lang in TRANSLATIONS else "ru"
    except Exception:
        return "ru"


def t(key: str, lang: str | None = None, **kwargs) -> str:
    """Перевод по ключу; недостающие ключи → ru → сам ключ."""
    code = lang or get_lang()
    text = TRANSLATIONS.get(code, {}).get(key)
    if text is None:
        text = TRANSLATIONS["ru"].get(key, key)
    if kwargs:
        return text.format(**kwargs)
    return text


def dist_label(internal_name: str, lang: str | None = None) -> str:
    return t(f"dist.{internal_name}", lang=lang)


def pluralize_rows(n: int, lang: str | None = None) -> str:
    code = lang or get_lang()
    if code == "en":
        return t("rows_1", lang=code) if n == 1 else t("rows_5", lang=code)
    if n % 10 == 1 and n % 100 != 11:
        return t("rows_1", lang=code)
    if 2 <= n % 10 <= 4 and (n % 100 < 10 or n % 100 >= 20):
        return t("rows_2", lang=code)
    return t("rows_5", lang=code)


def init_language_widgets():
    """Переключатель языка кнопками в сайдбаре. st.session_state['lang'] = 'ru'|'en'."""
    import streamlit as st

    if "lang" not in st.session_state:
        st.session_state.lang = "ru"

    def _set_lang(code: str):
        st.session_state.lang = code

    st.sidebar.markdown(f"**{t('lang_section_buttons')}**")
    col_ru, col_en = st.sidebar.columns(2)
    with col_ru:
        st.button(
            t("lang_ru"),
            key="lang_btn_ru",
            use_container_width=True,
            type="primary" if st.session_state.lang == "ru" else "secondary",
            on_click=_set_lang,
            args=("ru",),
        )
    with col_en:
        st.button(
            t("lang_en"),
            key="lang_btn_en",
            use_container_width=True,
            type="primary" if st.session_state.lang == "en" else "secondary",
            on_click=_set_lang,
            args=("en",),
        )

    st.sidebar.markdown("---")
