"""Generate a multi-page PDF report for an XRF project."""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from models.calculations import (
    compute_calibration_sheet, compute_analysis_sheet,
    descriptive_stats, fit_correction_factors,
)


def export_pdf(project, path: str) -> None:
    # Pre-compute calibration results once (analysis sheets reuse them)
    calib_results = {cs.element: compute_calibration_sheet(cs, project)
                     for cs in project.calibration_sheets}

    with PdfPages(path) as pdf:
        # ── cover page ──
        fig = plt.figure(figsize=(8.5, 11))
        fig.text(0.5, 0.85, "XRF Correction Factor Report", ha="center", size=22, weight="bold")
        fig.text(0.5, 0.78, project.name, ha="center", size=16)
        fig.text(0.5, 0.72, f"Project default diameter: {project.diameter_cm} cm  |  Area: {project.area_cm2:.4f} cm²",
                 ha="center", size=11)

        summary_lines = ["Calibration Sheets:"]
        for el, r in calib_results.items():
            summary_lines.append(f"   • {el} on {r.substrate}:   CF = {r.correction_factor:.4f} ± {r.cf_uncertainty:.4f}   "
                                 f"(n = {len(r.sample_results)},  mean err = {r.mean_pct_error:.2f}%,   area = {r.area_cm2:.4f} cm²)")
        summary_lines.append("")
        summary_lines.append("Analysis Sheets:")
        for ans in project.analysis_sheets:
            r = compute_analysis_sheet(ans, calib_results, project)
            summary_lines.append(f"   • {ans.name}  ({', '.join(ans.elements)}):   "
                                 f"mean err = {r.mean_pct_error:.2f}%,   n = {len(r.sample_results)},   area = {r.area_cm2:.4f} cm²")

        fig.text(0.1, 0.60, "\n".join(summary_lines), ha="left", va="top", size=10, family="monospace")
        pdf.savefig(fig); plt.close(fig)

        # ── calibration sheets ──
        for cs in project.calibration_sheets:
            r = calib_results[cs.element]
            _render_calibration_pages(pdf, r)

        # ── analysis sheets ──
        for ans in project.analysis_sheets:
            r = compute_analysis_sheet(ans, calib_results, project)
            _render_analysis_pages(pdf, r, ans, calib_results)


def _render_calibration_pages(pdf, r):
    ids   = [sr.sample_id for sr in r.sample_results]
    cfs   = [sr.corr_factor for sr in r.sample_results]
    mls   = [sr.mass_loading for sr in r.sample_results]
    errs  = [sr.pct_error for sr in r.sample_results]
    outl  = set(r.outlier_indices)
    colors = ["#d35400" if i in outl else "#2980b9" for i in range(len(ids))]

    fig, axes = plt.subplots(2, 2, figsize=(11, 8.5))
    fig.suptitle(f"{r.element} on {r.substrate}  —  CF = {r.correction_factor:.4f} ± {r.cf_uncertainty:.4f}",
                 weight="bold")

    ax = axes[0, 0]
    ax.bar(ids, cfs, color=colors)
    ax.axhline(r.correction_factor, ls="--", color="k")
    ax.set_ylabel("Correction Factor"); ax.set_title("CF per Sample")
    ax.tick_params(axis="x", rotation=45)

    ax = axes[0, 1]
    ax.scatter(mls, cfs, c=colors, s=60)
    fit = fit_correction_factors(mls, cfs, "linear")
    if fit:
        ax.plot(fit.x_fit, fit.y_fit, "r--", label=f"linear (R²={fit.r_squared:.3f})")
        ax.legend()
    ax.set_xlabel("Mass Loading (mg/cm²)"); ax.set_ylabel("CF")
    ax.set_title("CF vs. Mass Loading")

    ax = axes[1, 0]
    ax.bar(ids, errs, color=colors)
    ax.set_ylabel("% Error"); ax.set_title("Per-Sample % Error")
    ax.tick_params(axis="x", rotation=45)

    ax = axes[1, 1]; ax.axis("off")
    stats = descriptive_stats(cfs)
    err_stats = descriptive_stats(errs)
    txt = (
        f"n = {stats.get('n', 0)}\n"
        f"CF mean   = {stats.get('mean', 0):.4f}\n"
        f"CF σ      = {stats.get('std', 0):.4f}\n"
        f"CF CV%    = {stats.get('cv_pct', 0):.2f}\n"
        f"CF min    = {stats.get('min', 0):.4f}\n"
        f"CF max    = {stats.get('max', 0):.4f}\n"
        f"\n"
        f"% Error mean  = {err_stats.get('mean', 0):.2f}%\n"
        f"% Error max   = {err_stats.get('max', 0):.2f}%\n"
        f"\n"
        f"Outliers: {len(outl)}"
    )
    ax.text(0.0, 1.0, txt, va="top", family="monospace", size=10)

    fig.tight_layout()
    pdf.savefig(fig); plt.close(fig)


def _render_analysis_pages(pdf, r, ans, calib_results):
    ids = [sr.sample_id for sr in r.sample_results]
    mls = [sr.mass_loading for sr in r.sample_results]
    corr = [sr.corrected_total for sr in r.sample_results]
    errs = [sr.pct_error for sr in r.sample_results]
    sigs = [sr.sigma_corrected for sr in r.sample_results]
    outl = set(r.outlier_indices)
    colors = ["#d35400" if i in outl else "#27ae60" for i in range(len(ids))]

    fig, axes = plt.subplots(2, 2, figsize=(11, 8.5))
    cf_str = "  ".join(f"{el}={cf:.3f}" for el, cf in r.correction_factors.items())
    fig.suptitle(f"{r.name}  —  CFs: {cf_str}  —  mean err = {r.mean_pct_error:.2f}%", weight="bold")

    ax = axes[0, 0]
    ax.bar(ids, errs, color=colors)
    ax.set_ylabel("% Error"); ax.set_title("Per-Sample % Error")
    ax.tick_params(axis="x", rotation=45)

    ax = axes[0, 1]
    if mls and corr:
        ax.errorbar(mls, corr, yerr=sigs, fmt="o", color="#2c3e50",
                    ecolor="gray", capsize=3, markersize=6)
        lo, hi = min(mls + corr), max(mls + corr)
        ax.plot([lo, hi], [lo, hi], "k--", label="y = x")
        ax.legend()
    ax.set_xlabel("Measured (mg/cm²)"); ax.set_ylabel("Corrected (mg/cm²)")
    ax.set_title("Parity Plot")

    ax = axes[1, 0]
    bottoms = np.zeros(len(ids))
    cmap = ["#2980b9", "#27ae60", "#8e44ad", "#e67e22", "#c0392b"]
    for ei, el in enumerate(ans.elements):
        cf = r.correction_factors.get(el, 1.0)
        contribs = [sr.xrf_per_element.get(el, 0) * cf for sr in r.sample_results]
        ax.bar(ids, contribs, bottom=bottoms, color=cmap[ei % len(cmap)], label=el)
        bottoms += np.array(contribs)
    ax.plot(ids, mls, "kx", markersize=8, label="Measured")
    ax.legend(); ax.set_ylabel("Corrected Loading (mg/cm²)")
    ax.set_title("Element Contribution")
    ax.tick_params(axis="x", rotation=45)

    ax = axes[1, 1]; ax.axis("off")
    err_stats = descriptive_stats(errs)
    txt = (
        f"n = {len(ids)}\n"
        f"% Error mean   = {err_stats.get('mean', 0):.2f}%\n"
        f"% Error max    = {err_stats.get('max', 0):.2f}%\n"
        f"% Error σ      = {err_stats.get('std', 0):.2f}%\n"
        f"\n"
        f"Outliers: {len(outl)}\n"
        f"\n"
        f"Correction factors used:"
    )
    for el, cr in calib_results.items():
        if el in ans.elements:
            txt += f"\n  {el}: {cr.correction_factor:.4f} ± {cr.cf_uncertainty:.4f}"
    ax.text(0.0, 1.0, txt, va="top", family="monospace", size=10)

    fig.tight_layout()
    pdf.savefig(fig); plt.close(fig)
