import math
import numpy as np
from scipy import stats
from scipy.optimize import curve_fit
from dataclasses import dataclass
from typing import Optional


@dataclass
class CalibrationResult:
    sample_id: str
    mass_loading: float
    xrf_loading: float
    corr_factor: float
    corrected_loading: float
    pct_error: float
    is_outlier: bool = False


@dataclass
class CalibrationSheetResult:
    element: str
    substrate: str
    sample_results: list
    correction_factor: float
    cf_std: float
    cf_uncertainty: float
    mean_pct_error: float
    outlier_indices: list
    area_cm2: float


@dataclass
class AnalysisSampleResult:
    sample_id: str
    mass_loading: float
    xrf_per_element: dict
    xrf_total: float
    corrected_total: float
    pct_error: float
    sigma_corrected: float
    is_outlier: bool = False


@dataclass
class AnalysisSheetResult:
    name: str
    sample_results: list
    mean_pct_error: float
    correction_factors: dict
    outlier_indices: list
    area_cm2: float


@dataclass
class FitResult:
    model: str
    params: list
    param_errors: list
    r_squared: float
    x_fit: list
    y_fit: list


def compute_calibration_sheet(sheet, project, alpha: float = 0.05) -> CalibrationSheetResult:
    area = sheet.effective_area_cm2(project)

    # Pass 1: per-sample correction factors
    pre, cfs = [], []
    for s in sheet.samples:
        if s.xrf_loading <= 0:
            continue
        ml = sheet.mass_loading_of(s, project)
        cf = ml / s.xrf_loading
        pre.append((s, ml, cf))
        cfs.append(cf)

    if not cfs:
        return CalibrationSheetResult(
            element=sheet.element, substrate=sheet.substrate,
            sample_results=[], correction_factor=float("nan"),
            cf_std=float("nan"), cf_uncertainty=float("nan"),
            mean_pct_error=float("nan"), outlier_indices=[], area_cm2=area,
        )

    cf_arr = np.array(cfs)
    mean_cf = float(np.mean(cf_arr))
    cf_std = float(np.std(cf_arr, ddof=1)) if len(cf_arr) > 1 else 0.0
    cf_unc = cf_std / math.sqrt(len(cf_arr)) if len(cf_arr) > 1 else 0.0

    # Pass 2: validate each sample against the MEAN CF (the CF that gets applied in practice)
    results = []
    for s, ml, cf in pre:
        corr = s.xrf_loading * mean_cf
        err = abs(corr - ml) / ml * 100 if ml > 0 else 0.0
        results.append(CalibrationResult(
            sample_id=s.sample_id, mass_loading=ml, xrf_loading=s.xrf_loading,
            corr_factor=cf, corrected_loading=corr, pct_error=err,
        ))

    mean_err = float(np.mean([r.pct_error for r in results]))

    outlier_idx = _grubbs_outliers(cf_arr, alpha)
    for i, r in enumerate(results):
        r.is_outlier = i in outlier_idx

    return CalibrationSheetResult(
        element=sheet.element, substrate=sheet.substrate,
        sample_results=results, correction_factor=mean_cf,
        cf_std=cf_std, cf_uncertainty=cf_unc,
        mean_pct_error=mean_err, outlier_indices=outlier_idx, area_cm2=area,
    )


def compute_analysis_sheet(sheet, calib_results: dict, project, alpha: float = 0.05) -> AnalysisSheetResult:
    area = sheet.effective_area_cm2(project)
    sample_results, pct_errors = [], []

    for s in sheet.samples:
        ml = sheet.mass_loading_of(s, project)
        xrf_total = sum(s.xrf_loadings.get(el, 0.0) for el in sheet.elements)

        corrected = 0.0
        sigma_sq = 0.0
        for el in sheet.elements:
            xrf_el = s.xrf_loadings.get(el, 0.0)
            cr = calib_results.get(el)
            if cr is None:
                continue
            cf = cr.correction_factor
            corrected += xrf_el * cf
            sigma_xrf = 0.02 * xrf_el
            sigma_cf  = cr.cf_uncertainty
            sigma_sq += (sigma_xrf * cf) ** 2 + (xrf_el * sigma_cf) ** 2

        err = abs(corrected - ml) / ml * 100 if ml > 0 else 0.0
        pct_errors.append(err)

        sample_results.append(AnalysisSampleResult(
            sample_id=s.sample_id, mass_loading=ml,
            xrf_per_element={el: s.xrf_loadings.get(el, 0.0) for el in sheet.elements},
            xrf_total=xrf_total, corrected_total=corrected,
            pct_error=err, sigma_corrected=math.sqrt(sigma_sq),
        ))

    outlier_idx = _grubbs_outliers(np.array(pct_errors), alpha) if pct_errors else []
    for i, r in enumerate(sample_results):
        r.is_outlier = i in outlier_idx

    return AnalysisSheetResult(
        name=sheet.name, sample_results=sample_results,
        mean_pct_error=float(np.mean(pct_errors)) if pct_errors else float("nan"),
        correction_factors={el: calib_results[el].correction_factor
                            for el in sheet.elements if el in calib_results},
        outlier_indices=outlier_idx, area_cm2=area,
    )


def descriptive_stats(values: list) -> dict:
    if not values:
        return {}
    arr = np.array([v for v in values if not math.isnan(v)])
    if len(arr) == 0:
        return {}
    return {
        "n": len(arr),
        "mean": float(np.mean(arr)),
        "std": float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0,
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
        "median": float(np.median(arr)),
        "cv_pct": float(np.std(arr, ddof=1) / np.mean(arr) * 100) if np.mean(arr) != 0 and len(arr) > 1 else 0.0,
    }


def fit_correction_factors(xs: list, ys: list, model: str = "linear") -> Optional[FitResult]:
    x = np.array(xs)
    y = np.array(ys)
    if len(x) < 2:
        return None
    try:
        if model == "linear":
            def func(x, a, b): return a * x + b
            p0 = [0.0, float(np.mean(y))]
        else:
            def func(x, a, b, c): return a * x ** 2 + b * x + c
            p0 = [0.0, 0.0, float(np.mean(y))]

        popt, pcov = curve_fit(func, x, y, p0=p0)
        perr = np.sqrt(np.diag(pcov))
        y_pred = func(x, *popt)
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 1.0

        x_fit = np.linspace(x.min(), x.max(), 200).tolist()
        y_fit = func(np.array(x_fit), *popt).tolist()
        return FitResult(model=model, params=popt.tolist(), param_errors=perr.tolist(),
                         r_squared=float(r2), x_fit=x_fit, y_fit=y_fit)
    except Exception:
        return None


def _grubbs_outliers(arr: np.ndarray, alpha: float = 0.05) -> list:
    if len(arr) < 3:
        return []
    outliers = set()
    remaining = list(range(len(arr)))
    while True:
        vals = arr[remaining]
        if len(vals) < 3:
            break
        mean_, std_ = np.mean(vals), np.std(vals, ddof=1)
        if std_ == 0:
            break
        g_vals = np.abs(vals - mean_) / std_
        max_i = int(np.argmax(g_vals))
        g_stat = float(g_vals[max_i])
        n = len(vals)
        t_crit = stats.t.ppf(1 - alpha / (2 * n), df=n - 2)
        g_crit = (n - 1) / math.sqrt(n) * math.sqrt(t_crit ** 2 / (n - 2 + t_crit ** 2))
        if g_stat > g_crit:
            outliers.add(remaining[max_i])
            remaining.pop(max_i)
        else:
            break
    return sorted(outliers)
