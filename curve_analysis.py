"""Подгонка распределений, графики и составные кривые обеспеченности."""

from __future__ import annotations

from io import BytesIO

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy.stats as stats
from scipy.optimize import brentq
from sklearn.metrics import mean_absolute_error, max_error, r2_score

from distributions import (
    CustomDistributionAdapter,
    KrytskyMenkelAdapter,
    LMomentsDistributionAdapter,
    ScipyDistributionAdapter,
    anderson_darling_test,
    create_scipy_dist_from_lmoments,
    format_stat,
    km_coefficient_of_skewness,
    km_coefficient_of_variation,
)
from i18n import dist_label, t


NO_GROUP = "__no_group__"

PERCENT_LIST_DEFAULT = [
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


def teor_x_grid():
    range1 = np.arange(0.1, 1.1, 0.2)
    range2 = np.arange(1.1, 2.0, 0.3)
    range3 = np.arange(2.0, 98.0, 1.0)
    range4 = np.arange(98.0, 98.9, 0.3)
    range5 = np.arange(98.9, 99.9, 0.2)
    return np.concatenate([range1, range2, range3, range4, range5, [99.9]])


def scalefunc(x):
    return stats.norm.ppf(x / 100, loc=0, scale=1)


def build_empirical(series_df, values_col, index_col):
    """Хронологический ряд + эмпирическое распределение (как в app)."""
    data = series_df.copy().reset_index(drop=True)
    n = len(data)
    data["Ранг"] = np.arange(1, n + 1)
    data["Вероятность"] = data["Ранг"] / (n + 1)
    data["Обеспеченность P, %"] = round(data["Вероятность"] * 100, 2)
    data_to_merge = data.sort_values(by=values_col, ascending=False)
    data_to_merge = data_to_merge.drop(
        columns=["Вероятность", "Обеспеченность P, %", "Ранг"]
    )
    data_to_merge = data_to_merge.rename(columns={values_col: values_col + " (P)"})
    if index_col != NO_GROUP and index_col in data_to_merge.columns:
        data_to_merge = data_to_merge.rename(columns={index_col: index_col + " (P)"})
    data_to_merge["Ранг"] = np.arange(1, n + 1)
    data = data.merge(data_to_merge, on="Ранг")
    data = data.set_index("Ранг")
    return data


def make_cdf_func(selected_dist, params, distribution_name):
    """CDF в исходном масштабе наблюдений: F(x)=P(X<=x)."""
    if isinstance(selected_dist, ScipyDistributionAdapter):
        fitted = selected_dist._dist(*params)
        return fitted.cdf
    if isinstance(selected_dist, LMomentsDistributionAdapter):
        fitted = create_scipy_dist_from_lmoments(
            selected_dist._lmoments_name, params
        )
        return fitted.cdf
    if (
        isinstance(selected_dist, CustomDistributionAdapter)
        and "Гумбеля (Мом)" in distribution_name
    ):
        fitted = stats.gumbel_r(loc=params[0], scale=params[1])
        return fitted.cdf
    if isinstance(selected_dist, KrytskyMenkelAdapter):
        return lambda x, dist=selected_dist, p=params: dist.cdf_original(x, *p)
    return lambda x: np.nan


def distribution_moments(selected_dist, params, distribution_name):
    """Среднее, Cv, Cs для таблицы метрик."""
    try:
        if isinstance(selected_dist, ScipyDistributionAdapter):
            dist = selected_dist._dist(*params)
            mean = dist.mean()
            std = dist.std()
            return mean, format_stat(std / mean), format_stat(dist.stats(moments="s"))
        if isinstance(selected_dist, LMomentsDistributionAdapter):
            dist = create_scipy_dist_from_lmoments(
                selected_dist._lmoments_name, params
            )
            mean = dist.mean()
            std = dist.std()
            return mean, format_stat(std / mean), format_stat(dist.stats(moments="s"))
        if isinstance(selected_dist, KrytskyMenkelAdapter):
            γ, a, b = params
            mean = selected_dist.mean_original(γ, a, b)
            return (
                mean,
                format_stat(km_coefficient_of_variation(γ, a, b)),
                format_stat(km_coefficient_of_skewness(γ, a, b)),
            )
        if (
            isinstance(selected_dist, CustomDistributionAdapter)
            and "Гумбеля (Мом)" in distribution_name
        ):
            dist = stats.gumbel_r(loc=params[0], scale=params[1])
            mean = dist.mean()
            std = dist.std()
            return mean, format_stat(std / mean), format_stat(dist.stats(moments="s"))
    except Exception:
        pass
    err = t("error_label")
    return err, err, err


def fit_quality(data, values_col, selected_dist, params):
    """R², MAE, maxE, A-D для подобранного распределения."""
    predict = data["Вероятность"].apply(
        lambda x, dist=selected_dist, p=params: dist.ppf(1 - x, *p)
    )
    y_emp = data[values_col + " (P)"]
    r2 = r2_score(y_emp, predict)
    mae = mean_absolute_error(y_emp, predict)
    maxE = max_error(y_emp, predict)
    try:
        cdf_func = make_cdf_func(selected_dist, params, selected_dist.name)
        ad_stat = anderson_darling_test(data[values_col].values, cdf_func)
    except Exception:
        ad_stat = np.nan
    return r2, mae, maxE, ad_stat


def format_return_period(p_pct):
    """T = 100 / P% для таблицы и подписей."""
    t_years = 100.0 / float(p_pct)
    if abs(t_years - round(t_years)) < 1e-9:
        return str(int(round(t_years)))
    if t_years >= 10:
        return f"{t_years:.1f}"
    return f"{t_years:.2f}".rstrip("0").rstrip(".")


def apply_exceedance_axes(ax, values_col, title=None):
    ax.xaxis.grid(True)
    ax.set_xscale("function", functions=(scalefunc, lambda x: x))
    ax.set_xlabel(t("ensurance_pct"), fontsize=12)
    ax.set_ylabel(values_col, fontsize=12)
    ax.set_title(title or t("curve_title"), fontsize=14, pad=28)
    ax.set(xlim=(0.1, 99.9))
    ticks = [0.1, 0.5, 1, 2, 5, 10, 20, 25, 30, 40, 50, 60, 70, 80, 90, 95, 98, 99, 99.9]
    ax.set_xticks(ticks)
    ax.set_xticklabels(ticks)
    ax.tick_params(axis="x", labelsize=11)
    ax.tick_params(axis="y", labelsize=11)

    # Верхняя шкала: выбранные периоды (P = 100/T); без 40 и 25
    # 0.5% (T=200) и 25% (T=4) уже в ticks снизу — сетка xaxis.grid их рисует как остальные
    return_periods = [1000, 200, 100, 50, 20, 10, 5, 4, 2]
    return_p = [100.0 / tr for tr in return_periods]
    ax_top = ax.twiny()
    ax_top.set_xscale("function", functions=(scalefunc, lambda x: x))
    ax_top.set_xlim(ax.get_xlim())
    ax_top.set_xticks(return_p)
    ax_top.set_xticklabels([str(tr) for tr in return_periods])
    ax_top.set_xlabel(t("return_period_years"), fontsize=12)
    ax_top.tick_params(axis="x", labelsize=11)
    return ax_top


def fig_to_png_bytes(fig):
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def compound_exceedance_pct(x, cdf_funcs, ns):
    """
    Составная обеспеченность, %:
    P = 100 - 100 * Σ(ni * Fi(x)) / Σ ni
    """
    total = float(sum(ns))
    if total <= 0:
        return np.nan
    x = np.asarray(x, dtype=float)
    weighted = np.zeros_like(x, dtype=float)
    for cdf, n in zip(cdf_funcs, ns):
        fi = np.vectorize(cdf)(x)
        weighted += n * fi
    return 100.0 - 100.0 * weighted / total


def compound_ppf(p_pct, cdf_funcs, ns, x_lo, x_hi):
    """Квантиль составной кривой: значение x при обеспеченности p_pct %."""
    target = float(p_pct)

    def objective(x):
        return compound_exceedance_pct(x, cdf_funcs, ns) - target

    lo, hi = float(x_lo), float(x_hi)
    # чуть расширить диапазон поиска
    span = max(hi - lo, abs(hi), abs(lo), 1.0)
    lo_b = lo - 0.25 * span
    hi_b = hi + 0.25 * span
    try:
        f_lo = objective(lo_b)
        f_hi = objective(hi_b)
        if np.sign(f_lo) == np.sign(f_hi):
            # грубый перебор границ
            for k in range(1, 8):
                lo_b = lo - k * span
                hi_b = hi + k * span
                f_lo = objective(lo_b)
                f_hi = objective(hi_b)
                if np.sign(f_lo) != np.sign(f_hi):
                    break
            else:
                return np.nan
        return float(brentq(objective, lo_b, hi_b, maxiter=200))
    except Exception:
        return np.nan


def empirical_column_metrics(data, values_col):
    mean = data[values_col].mean()
    std = data[values_col].std()
    cv = std / mean if mean else np.nan
    cs = stats.skew(data[values_col])
    return mean, cv, cs
