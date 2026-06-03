import math
import numpy as np
from scipy import stats
from scipy.optimize import curve_fit
from dataclasses import dataclass, field
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
    mass_loading: float          # measured, mg/cm²
    measured_mass: float         # measured, mg  (= mass_loading × area)
    xrf_per_element: dict        # raw XRF loading per element, mg/cm²
    xrf_total: float             # sum of XRF loadings, mg/cm²

    # ── Active regime (using element_cf_sources settings) ──
    corrected_per_element: dict       # mg/cm²
    corrected_total: float            # mg/cm²
    corrected_mass_per_element: dict  # mg
    corrected_mass_total: float       # mg
    pct_error: float
    sigma_corrected: float

    # ── Reference regime (all calibration CFs, for comparison) ──
    ref_corrected_total: float        # mg/cm²
    ref_corrected_mass_total: float   # mg
    ref_pct_error: float

    # ── Per-sample self CF (informational, always computed) ──
    self_cf: float = float("nan")     # mass_loading / xrf_total for this sample

    # Capacity-based mass loading regime (element-specific):
    #   active elements:    xrf_el × (mean_practical_sc / expected_sc_el)
    #   non-active elements: xrf_el × residual capacity CF (same logic as residual self CF)
    cap_regime_loading: float = float("nan")              # mg/cm² (total)
    cap_regime_mass: float = float("nan")                 # mg (total)
    cap_regime_per_element: Optional[dict] = None         # element → mg/cm²
    cap_regime_mass_per_element: Optional[dict] = None    # element → mg

    is_outlier: bool = False


@dataclass
class AnalysisSheetResult:
    name: str
    sample_results: list
    mean_pct_error: float            # active regime
    ref_mean_pct_error: float        # reference (calibration-only) regime
    correction_factors: dict         # active CFs per element
    ref_correction_factors: dict     # calibration-sheet CFs per element
    outlier_indices: list
    area_cm2: float
    # Sheet-level self CF (mean across all samples)
    self_cf: float = float("nan")
    self_cf_std: float = float("nan")
    self_cf_uncertainty: float = float("nan")
    mean_practical_sc: float = float("nan")
    practical_sc_std: float = float("nan")
    cap_correction_factors: Optional[dict] = None   # element → capacity-derived CF
    cap_residual_cf: float = float("nan")            # residual CF for non-active elements
    cap_mean_pct_error: float = float("nan")         # cap regime mean error (non-outlier)


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

    # Collect all valid samples
    pre = []
    for s in sheet.samples:
        if s.xrf_loading <= 0:
            continue
        ml = sheet.mass_loading_of(s, project)
        pre.append((s, ml, ml / s.xrf_loading))

    if not pre:
        return CalibrationSheetResult(
            element=sheet.element, substrate=sheet.substrate,
            sample_results=[], correction_factor=float("nan"),
            cf_std=float("nan"), cf_uncertainty=float("nan"),
            mean_pct_error=float("nan"), outlier_indices=[], area_cm2=area,
        )

    # Separate manually-excluded samples; run Grubbs only on the rest
    non_excl = [(i, s, ml, cf) for i, (s, ml, cf) in enumerate(pre)
                if not getattr(s, "is_excluded", False)]
    non_excl_cfs = np.array([cf for _, _, _, cf in non_excl])
    grubbs_local = set(_grubbs_outliers(non_excl_cfs, alpha)) if len(non_excl_cfs) >= 3 else set()
    # Map Grubbs indices back to pre-list positions
    grubbs_pre = {non_excl[j][0] for j in grubbs_local}

    # Combined outlier set (manual + Grubbs)
    outlier_pre = {i for i, (s, _, _) in enumerate(pre)
                   if getattr(s, "is_excluded", False)} | grubbs_pre

    # Compute mean CF from clean samples only
    clean_cfs = [cf for i, (_, _, cf) in enumerate(pre) if i not in outlier_pre]
    if not clean_cfs:
        clean_cfs = [cf for _, _, cf in pre]   # fallback: use all if everything is excluded
    mean_cf = float(np.mean(clean_cfs))
    cf_std  = float(np.std(clean_cfs, ddof=1)) if len(clean_cfs) > 1 else 0.0
    cf_unc  = cf_std / math.sqrt(len(clean_cfs)) if len(clean_cfs) > 1 else 0.0

    # Build per-sample results using the clean mean CF
    results = []
    for i, (s, ml, cf) in enumerate(pre):
        corr = s.xrf_loading * mean_cf
        err  = abs(corr - ml) / ml * 100 if ml > 0 else 0.0
        r    = CalibrationResult(
            sample_id=s.sample_id, mass_loading=ml, xrf_loading=s.xrf_loading,
            corr_factor=cf, corrected_loading=corr, pct_error=err,
        )
        r.is_outlier = i in outlier_pre
        results.append(r)

    # mean error excludes outliers
    clean_errs = [r.pct_error for i, r in enumerate(results) if i not in outlier_pre]
    mean_err   = float(np.mean(clean_errs)) if clean_errs else float(np.mean([r.pct_error for r in results]))

    # outlier_indices are positions in results list
    outlier_idx = sorted(outlier_pre)

    return CalibrationSheetResult(
        element=sheet.element, substrate=sheet.substrate,
        sample_results=results, correction_factor=mean_cf,
        cf_std=cf_std, cf_uncertainty=cf_unc,
        mean_pct_error=mean_err, outlier_indices=outlier_idx, area_cm2=area,
    )


def compute_analysis_sheet(sheet, calib_results: dict, project, alpha: float = 0.05) -> AnalysisSheetResult:
    area = sheet.effective_area_cm2(project)
    element_cf_sources = getattr(sheet, "element_cf_sources", {})

    # ── Reference CFs (calibration sheets) ──
    ref_cfs = {el: (calib_results[el].correction_factor if el in calib_results else float("nan"))
               for el in sheet.elements}

    # ── Custom (manual) CFs ──
    custom_cfs = {}
    for el in sheet.elements:
        src = element_cf_sources.get(el, "calibration")
        if src not in ("calibration", "self"):
            try:
                custom_cfs[el] = float(src)
            except (ValueError, TypeError):
                custom_cfs[el] = ref_cfs.get(el, 1.0)

    # ── Elements that use the self-derived CF ──
    self_els = [el for el in sheet.elements
                if element_cf_sources.get(el, "calibration") == "self"]

    # ── Residual self CF: subtract calibration + custom contributions first ──
    # When self_els is non-empty, CF_self = (mass_loading - known_contributions) / xrf_self_total
    # When self_els is empty, fall back to global mean(mass_loading / xrf_total) for reference display
    self_cfs_per_sample = []
    for s in sheet.samples:
        ml = sheet.mass_loading_of(s, project)
        if self_els:
            known = sum(
                s.xrf_loadings.get(el, 0.0) * (_safe_cf(ref_cfs.get(el))
                                                if element_cf_sources.get(el, "calibration") == "calibration"
                                                else custom_cfs.get(el, 1.0))
                for el in sheet.elements
                if element_cf_sources.get(el, "calibration") != "self"
            )
            xrf_self = sum(s.xrf_loadings.get(el, 0.0) for el in self_els)
            residual  = ml - known
            cf_i = residual / xrf_self if xrf_self > 0 else float("nan")
        else:
            xrf_total = sum(s.xrf_loadings.get(el, 0.0) for el in sheet.elements)
            cf_i = ml / xrf_total if xrf_total > 0 and ml > 0 else float("nan")
        self_cfs_per_sample.append(cf_i)

    # Mean self CF excludes manually-excluded samples
    valid_self  = [cf for j, cf in enumerate(self_cfs_per_sample)
                   if not math.isnan(cf) and not getattr(sheet.samples[j], "is_excluded", False)]
    mean_self_cf = float(np.mean(valid_self))        if valid_self           else float("nan")
    self_cf_std  = float(np.std(valid_self, ddof=1)) if len(valid_self) > 1  else 0.0
    self_cf_unc  = self_cf_std / math.sqrt(len(valid_self)) if len(valid_self) > 1 else 0.0

    # ── Active CFs ──
    active_cfs = {}
    for el in sheet.elements:
        src = element_cf_sources.get(el, "calibration")
        if src == "calibration":
            active_cfs[el] = ref_cfs[el]
        elif src == "self":
            active_cfs[el] = mean_self_cf
        else:
            active_cfs[el] = custom_cfs.get(el, ref_cfs.get(el, float("nan")))

    # ── Per-sample results ──
    sample_results, pct_errors = [], []
    for i, s in enumerate(sheet.samples):
        ml            = sheet.mass_loading_of(s, project)
        measured_mass = ml * area
        xrf_total     = sum(s.xrf_loadings.get(el, 0.0) for el in sheet.elements)

        corrected, sigma_sq = 0.0, 0.0
        corrected_per_element, corrected_mass_per_element = {}, {}
        for el in sheet.elements:
            xrf_el = s.xrf_loadings.get(el, 0.0)
            cf     = _safe_cf(active_cfs.get(el))
            el_loading = xrf_el * cf
            corrected += el_loading
            corrected_per_element[el]      = el_loading
            corrected_mass_per_element[el] = el_loading * area
            src = element_cf_sources.get(el, "calibration")
            cr  = calib_results.get(el)
            if cr is not None and src == "calibration":
                sigma_sq += (0.02 * xrf_el * cf) ** 2 + (xrf_el * cr.cf_uncertainty) ** 2
            else:
                sigma_sq += (0.02 * xrf_el * cf) ** 2

        err      = abs(corrected - ml) / ml * 100 if ml > 0 else 0.0
        ref_corr = sum(s.xrf_loadings.get(el, 0.0) * _safe_cf(ref_cfs[el])
                       for el in sheet.elements)
        ref_err  = abs(ref_corr - ml) / ml * 100 if ml > 0 else 0.0
        pct_errors.append(err)

        sample_results.append(AnalysisSampleResult(
            sample_id=s.sample_id, mass_loading=ml, measured_mass=measured_mass,
            xrf_per_element={el: s.xrf_loadings.get(el, 0.0) for el in sheet.elements},
            xrf_total=xrf_total,
            corrected_per_element=corrected_per_element, corrected_total=corrected,
            corrected_mass_per_element=corrected_mass_per_element,
            corrected_mass_total=corrected * area,
            pct_error=err, sigma_corrected=math.sqrt(sigma_sq),
            ref_corrected_total=ref_corr, ref_corrected_mass_total=ref_corr * area,
            ref_pct_error=ref_err, self_cf=self_cfs_per_sample[i],
            # cap_regime_loading filled in below after mean_psc is known
        ))

    # Grubbs runs on non-manually-excluded samples only
    non_excl_idx = [j for j, s in enumerate(sheet.samples) if not getattr(s, "is_excluded", False)
                    and j < len(sample_results)]
    non_excl_errs = np.array([pct_errors[j] for j in non_excl_idx]) if non_excl_idx else np.array([])
    grubbs_local  = set(_grubbs_outliers(non_excl_errs, alpha)) if len(non_excl_errs) >= 3 else set()
    grubbs_pre    = {non_excl_idx[j] for j in grubbs_local}
    manual_excl   = {j for j, s in enumerate(sheet.samples)
                     if getattr(s, "is_excluded", False) and j < len(sample_results)}
    outlier_idx   = sorted(grubbs_pre | manual_excl)

    for i, r in enumerate(sample_results):
        r.is_outlier = i in outlier_idx

    ref_errors = [sr.ref_pct_error for sr in sample_results]
    clean_errs = [pct_errors[j] for j in range(len(sample_results)) if j not in outlier_idx]

    # Practical SC stats (non-excluded samples)
    psc_vals = [getattr(sheet.samples[j], "practical_specific_capacity", float("nan"))
                for j in range(len(sample_results)) if j not in outlier_idx]
    psc_vals = [v for v in psc_vals if not math.isnan(v)]
    mean_psc = float(np.mean(psc_vals))        if psc_vals        else float("nan")
    psc_std  = float(np.std(psc_vals, ddof=1)) if len(psc_vals)>1 else 0.0

    # ── Capacity-based mass-loading regime (element-specific) ──
    # Active elements (expected SC defined): cap CF = mean_practical_sc / expected_sc_el.
    # Non-active elements: residual capacity CF, computed like the residual self CF
    #   residual_i = mass_loading_i - Σ(active xrf_el × cap_cf_el),  CF = residual / xrf_nonactive.
    esc = getattr(sheet, "element_specific_capacities", {})
    cap_active_els = [el for el in sheet.elements
                      if el in esc and not math.isnan(esc.get(el, float("nan"))) and esc.get(el, 0) > 0]
    cap_nonactive_els = [el for el in sheet.elements if el not in cap_active_els]

    cap_cf, cap_residual_cf = {}, float("nan")
    if cap_active_els and not math.isnan(mean_psc) and mean_psc > 0:
        for el in cap_active_els:
            cap_cf[el] = mean_psc / esc[el]

        if cap_nonactive_els:
            residual_cfs = []
            for j, s in enumerate(sheet.samples):
                if j in outlier_idx or j >= len(sample_results):
                    continue
                ml_j  = sample_results[j].mass_loading
                known = sum(s.xrf_loadings.get(el, 0.0) * cap_cf[el] for el in cap_active_els)
                xrf_non = sum(s.xrf_loadings.get(el, 0.0) for el in cap_nonactive_els)
                if xrf_non > 0:
                    residual_cfs.append((ml_j - known) / xrf_non)
            cap_residual_cf = float(np.mean(residual_cfs)) if residual_cfs else float("nan")
            for el in cap_nonactive_els:
                cap_cf[el] = cap_residual_cf

        for j, sr in enumerate(sample_results):
            s = sheet.samples[j]
            cap_per_el, cap_mass_per_el, cap_load = {}, {}, 0.0
            for el in sheet.elements:
                cf = cap_cf.get(el, float("nan"))
                contrib = s.xrf_loadings.get(el, 0.0) * (cf if not math.isnan(cf) else 0.0)
                cap_per_el[el]      = contrib
                cap_mass_per_el[el] = contrib * area
                cap_load += contrib
            sr.cap_regime_per_element      = cap_per_el
            sr.cap_regime_mass_per_element = cap_mass_per_el
            sr.cap_regime_loading          = cap_load
            sr.cap_regime_mass             = cap_load * area
    else:
        for sr in sample_results:
            sr.cap_regime_loading = float("nan")
            sr.cap_regime_mass    = float("nan")

    # cap regime mean error (non-outlier samples)
    cap_errs = []
    for j, sr in enumerate(sample_results):
        if j in outlier_idx or math.isnan(sr.cap_regime_loading):
            continue
        ml_j = sr.mass_loading
        if ml_j > 0:
            cap_errs.append(abs(sr.cap_regime_loading - ml_j) / ml_j * 100)
    cap_mean_err = float(np.mean(cap_errs)) if cap_errs else float("nan")

    return AnalysisSheetResult(
        name=sheet.name, sample_results=sample_results,
        mean_pct_error=float(np.mean(clean_errs)) if clean_errs else float("nan"),
        ref_mean_pct_error=float(np.mean(ref_errors)) if ref_errors else float("nan"),
        correction_factors=active_cfs, ref_correction_factors=ref_cfs,
        outlier_indices=outlier_idx, area_cm2=area,
        self_cf=mean_self_cf, self_cf_std=self_cf_std, self_cf_uncertainty=self_cf_unc,
        mean_practical_sc=mean_psc, practical_sc_std=psc_std,
        cap_correction_factors=(cap_cf or None), cap_residual_cf=cap_residual_cf,
        cap_mean_pct_error=cap_mean_err,
    )


def compute_all_regimes(sheet, calib_results: dict, project) -> list:
    """Return a list of regime dicts for comparison plots.

    Each entry: {name, element_cfs, samples: [{sample_id, corrected_total,
                                               corrected_mass, pct_error}]}
    Regimes always included: 'All calibration', 'All self (global)'.
    'Active' is appended only when it differs from both baselines.
    """
    area = sheet.effective_area_cm2(project)
    element_cf_sources = getattr(sheet, "element_cf_sources", {})

    # Reference CFs
    ref_cfs = {el: (calib_results[el].correction_factor if el in calib_results else float("nan"))
               for el in sheet.elements}

    # Global self CF (mass_loading / xrf_total, no residual adjustment)
    global_self_vals = []
    for s in sheet.samples:
        ml        = sheet.mass_loading_of(s, project)
        xrf_total = sum(s.xrf_loadings.get(el, 0.0) for el in sheet.elements)
        if xrf_total > 0 and ml > 0:
            global_self_vals.append(ml / xrf_total)
    mean_global_self = float(np.mean(global_self_vals)) if global_self_vals else float("nan")

    # Active CFs (from compute_analysis_sheet to get the residual self CF)
    r_active = compute_analysis_sheet(sheet, calib_results, project)
    active_cfs = r_active.correction_factors

    def _apply_cfs(cfs_dict):
        rows = []
        for s in sheet.samples:
            ml   = sheet.mass_loading_of(s, project)
            corr = sum(s.xrf_loadings.get(el, 0.0) * _safe_cf(cfs_dict.get(el))
                       for el in sheet.elements)
            rows.append({
                "sample_id":       s.sample_id,
                "corrected_total": corr,
                "corrected_mass":  corr * area,
                "pct_error":       abs(corr - ml) / ml * 100 if ml > 0 else 0.0,
            })
        return rows

    regimes = []

    calib_cfs = {el: ref_cfs[el] for el in sheet.elements}
    regimes.append({
        "name":         "All calibration",
        "element_cfs":  calib_cfs,
        "samples":      _apply_cfs(calib_cfs),
    })

    self_cfs = {el: mean_global_self for el in sheet.elements}
    regimes.append({
        "name":        f"All self  (CF={mean_global_self:.4f})",
        "element_cfs": self_cfs,
        "samples":     _apply_cfs(self_cfs),
    })

    # Capacity regime: element-specific (active = mean_psc / expected_sc, non-active = residual CF)
    if not math.isnan(r_active.mean_practical_sc) and r_active.cap_correction_factors:
        cap_rows = []
        for j, sr in enumerate(r_active.sample_results):
            ml = sheet.mass_loading_of(sheet.samples[j], project)
            cap_load = sr.cap_regime_loading
            err = abs(cap_load - ml) / ml * 100 if ml > 0 and not math.isnan(cap_load) else 0.0
            cap_rows.append({"sample_id": sr.sample_id, "corrected_total": cap_load,
                             "corrected_mass": sr.cap_regime_mass, "pct_error": err})
        regimes.append({
            "name":        f"Capacity  (mean prac. SC = {r_active.mean_practical_sc:.1f} mAh/g)",
            "element_cfs": dict(r_active.cap_correction_factors),
            "samples":     cap_rows,
        })

    # Add Active only if it differs from both baselines
    if active_cfs != calib_cfs and active_cfs != self_cfs:
        src_tags = []
        for el in sheet.elements:
            src = element_cf_sources.get(el, "calibration")
            tag = "calib" if src == "calibration" else ("self*" if src == "self" else "custom")
            src_tags.append(f"{el}:{tag}")
        regimes.append({
            "name":        f"Active  ({', '.join(src_tags)})",
            "element_cfs": active_cfs,
            "samples":     _apply_cfs(active_cfs),
        })

    return regimes


def _safe_cf(cf):
    """Return cf if finite, else 1.0 (avoids NaN propagation when calib sheet is missing)."""
    return cf if cf is not None and not math.isnan(cf) else 1.0


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
