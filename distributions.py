"""Распределения, адаптеры и связанные расчёты."""

import math
from abc import ABC, abstractmethod
from math import pi

import numpy as np
import scipy.stats as stats
from lmoments3 import distr
from scipy.optimize import minimize
from scipy.special import gammainc, gammaincinv
from sympy import EulerGamma


def anderson_darling_test(data, cdf_func):
    """
    Anderson-Darling тест для сравнения распределений.
    Возвращает A-D статистику (чем меньше, тем лучше).
    """
    n = len(data)
    sorted_data = np.sort(data)

    cdf_values = np.vectorize(cdf_func)(sorted_data)
    cdf_values = np.clip(cdf_values, 1e-12, 1 - 1e-12)

    i = np.arange(1, n + 1)
    term = (2 * i - 1) * (np.log(cdf_values) + np.log(1 - cdf_values[::-1]))
    return -n - (1 / n) * np.sum(term)


def format_stat(value):
    """Форматирует статистику: заменяет nan/inf на локализованный маркер."""
    if np.isnan(value) or np.isinf(value):
        try:
            from i18n import t

            return t("stat_undefined")
        except Exception:
            return "Не существует"
    return value


# --- Крицкий–Менкель ---

def km_log_pdf(k, γ, a, b):
    return (
        γ * math.log(γ)
        - (γ / b) * math.log(a)
        - math.lgamma(γ)
        - math.log(b)
        - γ * (k / a) ** (1 / b)
        + (γ / b - 1) * math.log(k)
    )


def km_pdf(k, γ, a, b):
    """Функция плотности с защитой от переполнения."""
    try:
        return math.exp(km_log_pdf(k, γ, a, b))
    except (OverflowError, ValueError):
        return 0.0


def km_cdf(k, γ, a, b):
    """CDF Крицкого–Менкеля через нормированную неполную гамма-функцию."""
    if k <= 0:
        return 0.0
    try:
        return float(np.clip(gammainc(γ, γ * (k / a) ** (1.0 / b)), 0.0, 1.0))
    except (ValueError, OverflowError, ZeroDivisionError):
        return float("nan")


def log_likelihood(params, data):
    """Логарифмическое правдоподобие Крицкого–Менкеля."""
    γ, a, b = params
    if γ <= 1e-10 or a <= 1e-10 or b <= 1e-10:
        return -1e10
    total = 0.0
    for z in data:
        if z <= 0:
            continue
        try:
            total += km_log_pdf(z, γ, a, b)
        except (ValueError, OverflowError):
            return -1e10
    if not math.isfinite(total):
        return -1e10
    return total


def _km_initial_starts(z):
    """Старты ММП; для малого Cv — большие γ / малые b."""
    cv = float(np.std(z, ddof=0))
    starts = [
        [2.0, 1.0, 1.0],
        [1.0, 1.0, 1.0],
        [5.0, 1.0, 0.5],
        [10.0, 1.0, 1.0],
        [20.0, 1.0, 0.5],
        [50.0, 1.0, 0.3],
        [100.0, 1.0, 0.2],
        [200.0, 1.0, 0.1],
        [5.0, 1.0, 2.0],
        [2.0, 1.0, 0.3],
    ]
    if cv < 0.05:
        starts.extend(
            [
                [100.0, 1.0, 0.05],
                [300.0, 1.0, 0.05],
                [500.0, 1.0, 0.03],
                [800.0, 1.0, 0.02],
                [200.0, 1.0, 0.08],
            ]
        )
    return starts


def km_fit_normalized(data, initial_params=None):
    """
    Подбор на данных, нормированных на среднее (как до коммита 3c456363).
    Возвращает (params, scaler).
    """
    data = np.asarray(data, dtype=float)
    scaler = float(np.mean(data))
    z = data / scaler

    starts = _km_initial_starts(z)
    if initial_params is not None:
        starts = [list(map(float, initial_params))] + starts

    best = None
    for start in starts:
        result = minimize(
            lambda params: -log_likelihood(params, z),
            start,
            method="L-BFGS-B",
            bounds=[(1e-8, None), (1e-8, None), (1e-8, None)],
            options={"maxiter": 15000, "ftol": 1e-14},
        )
        if not np.all(np.isfinite(result.x)):
            continue
        if best is None or result.fun < best.fun:
            best = result

    if best is None:
        raise RuntimeError("Не удалось подобрать параметры Крицкого–Менкеля")
    return best.x, scaler


def km_fit(data, initial_params=None):
    """Совместимость: возвращает только параметры (на нормированной шкале)."""
    params, _scaler = km_fit_normalized(data, initial_params=initial_params)
    return params


def _km_log_raw_moment(r, γ, a, b):
    """log E[Z^r] на шкале параметров: a^r * Γ(γ+r b) / (Γ(γ) γ^{r b})."""
    γ, a, b = float(γ), float(a), float(b)
    rb = float(r) * b
    if γ <= 0 or a <= 0 or b <= 0 or (γ + rb) <= 0:
        return float("nan")
    return (
        float(r) * math.log(a)
        + math.lgamma(γ + rb)
        - math.lgamma(γ)
        - rb * math.log(γ)
    )


def km_raw_moment(r, γ, a, b):
    """Момент E[Z^r] на шкале параметров."""
    log_m = _km_log_raw_moment(r, γ, a, b)
    if not math.isfinite(log_m):
        return float("nan")
    try:
        return math.exp(log_m)
    except OverflowError:
        return float("inf")


def km_mean(γ, a, b):
    """Математическое ожидание на шкале параметров (нормированной)."""
    return km_raw_moment(1, γ, a, b)


def km_variance(γ, a, b):
    """Дисперсия на шкале параметров."""
    log_m1 = _km_log_raw_moment(1, γ, a, b)
    log_m2 = _km_log_raw_moment(2, γ, a, b)
    if not (math.isfinite(log_m1) and math.isfinite(log_m2)):
        return float("nan")
    # Var = μ² (E[Z²]/μ² - 1) — устойчивее при малом Cv
    ratio = math.exp(log_m2 - 2.0 * log_m1)
    var = math.exp(2.0 * log_m1) * (ratio - 1.0)
    if not math.isfinite(var) or var < 0:
        return float("nan")
    return var


def km_std(γ, a, b):
    """Среднеквадратическое отклонение."""
    var = km_variance(γ, a, b)
    if (not math.isfinite(var)) or var < 0:
        return float("nan")
    return math.sqrt(var)


def km_coefficient_of_variation(γ, a, b):
    """Коэффициент вариации (безразмерный)."""
    log_m1 = _km_log_raw_moment(1, γ, a, b)
    log_m2 = _km_log_raw_moment(2, γ, a, b)
    if not (math.isfinite(log_m1) and math.isfinite(log_m2)):
        return float("nan")
    ratio = math.exp(log_m2 - 2.0 * log_m1)
    if not math.isfinite(ratio) or ratio < 1.0:
        return float("nan")
    return math.sqrt(ratio - 1.0)


def km_coefficient_of_skewness(γ, a, b):
    """Коэффициент асимметрии (безразмерный)."""
    log_m1 = _km_log_raw_moment(1, γ, a, b)
    log_m2 = _km_log_raw_moment(2, γ, a, b)
    log_m3 = _km_log_raw_moment(3, γ, a, b)
    if not all(math.isfinite(x) for x in (log_m1, log_m2, log_m3)):
        return float("nan")
    # μ3/μ³ = m3/μ³ - 3 m2/μ² + 2; Cs = (μ3/μ³) / Cv³
    r2 = math.exp(log_m2 - 2.0 * log_m1)
    r3 = math.exp(log_m3 - 3.0 * log_m1)
    if not math.isfinite(r2) or r2 <= 1.0:
        return float("nan")
    cv = math.sqrt(r2 - 1.0)
    if cv < 1e-15:
        return float("nan")
    skew_over_mean3 = r3 - 3.0 * r2 + 2.0
    return skew_over_mean3 / (cv**3)


def make_km_ppf(scaler, γ=None, a=None, b=None):
    """PPF Крицкого–Менкеля через gammaincinv; результат в исходном масштабе."""

    def km_ppf(p, γ_, a_, b_):
        p = float(np.clip(p, 1e-12, 1.0 - 1e-12))
        u = float(gammaincinv(float(γ_), p))
        z = float(a_) * (u / float(γ_)) ** float(b_)
        return z * scaler

    return km_ppf


# --- Гумбель (метод моментов) ---

def gumbel_moments_fit(data):
    """Параметры распределения Гумбеля методом моментов."""
    mean = np.mean(data)
    std = np.std(data, ddof=0)
    scale = std * (6 ** (1 / 2)) / pi
    loc = mean - float(EulerGamma) * scale
    return [loc, scale]


def gumbel_moments_ppf(x, loc, scale):
    """Квантильная функция распределения Гумбеля."""
    return stats.gumbel_r.ppf(x, loc=loc, scale=scale)


# --- Адаптеры ---

class DistributionAdapter(ABC):
    @abstractmethod
    def fit(self, data):
        """Возвращает параметры распределения."""

    @abstractmethod
    def ppf(self, x, *params):
        """Квантильная функция."""

    @property
    @abstractmethod
    def name(self):
        """Название распределения для отображения."""


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


class KrytskyMenkelAdapter(DistributionAdapter):
    """
    Крицкий–Менкель с нормировкой на среднее:
    fit на z=x/mean, ppf/cdf/mean возвращают исходный масштаб.
    """

    def __init__(self, display_name="Крицкого-Менкеля (ММП)"):
        self._display_name = display_name
        self.scaler = 1.0
        self._ppf = None
        self._params = None

    def fit(self, data):
        params, scaler = km_fit_normalized(data)
        self.scaler = float(scaler)
        self._params = tuple(map(float, params))
        self._ppf = make_km_ppf(self.scaler, *self._params)
        return params

    def ppf(self, x, *params):
        params_t = tuple(map(float, params))
        if self._ppf is None or params_t != self._params:
            self._params = params_t
            self._ppf = make_km_ppf(self.scaler, *params_t)
        return self._ppf(x, *params_t)

    def cdf_original(self, x, *params):
        """CDF в исходном масштабе наблюдений."""
        return km_cdf(x / self.scaler, *params)

    def mean_original(self, *params):
        """Математическое ожидание в исходном масштабе."""
        m = km_mean(*params)
        # после нормировки на среднее E[Z]≈1; если интеграл сорвался — берём scaler
        if (not math.isfinite(m)) or abs(m) < 1e-6:
            return self.scaler
        return m * self.scaler

    @property
    def name(self):
        return self._display_name


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

    @staticmethod
    def krytsky_menkel(display_name="Крицкого-Менкеля (ММП)"):
        return KrytskyMenkelAdapter(display_name)


def create_scipy_dist_from_lmoments(lmoments_name, params):
    """Создает scipy-распределение из параметров L-moments."""
    if lmoments_name == "gum":
        return stats.gumbel_r(loc=params[0], scale=params[1])
    if lmoments_name == "pe3":
        return stats.pearson3(skew=params[0], loc=params[1], scale=params[2])
    if lmoments_name == "gev":
        return stats.genextreme(c=params[0], loc=params[1], scale=params[2])
    raise ValueError(f"Неизвестное L-moments распределение: {lmoments_name}")


def build_distributions(data_min=None, data_max=None):
    """Словарь доступных распределений для UI.

    data_min/data_max сохранены для совместимости вызова; КМ использует
    нормировку на среднее внутри KrytskyMenkelAdapter.
    """
    return {
        "Гумбеля (ММП)": DistributionFactory.scipy("gumbel_r", "Гумбеля (ММП)"),
        "Пирсона 3 типа (ММП)": DistributionFactory.scipy(
            "pearson3", "Пирсона 3 типа (ММП)"
        ),
        "Обобщенное (ММП)": DistributionFactory.scipy(
            "genextreme", "Обобщенное (ММП)"
        ),
        "Крицкого-Менкеля (ММП)": DistributionFactory.krytsky_menkel(),
        "Гумбеля (Мом)": DistributionFactory.custom(
            gumbel_moments_fit, gumbel_moments_ppf, "Гумбеля (Мом)"
        ),
        "Гумбеля (L-мом)": DistributionFactory.lmoments("gum", "Гумбеля (L-мом)"),
        "Пирсона 3 типа (L-мом)": DistributionFactory.lmoments(
            "pe3", "Пирсона 3 типа (L-мом)"
        ),
        "Обобщенное (L-мом)": DistributionFactory.lmoments("gev", "Обобщенное (L-мом)"),
    }
