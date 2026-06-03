import math
from dataclasses import dataclass, field
from typing import Optional


# input_mode values
INPUT_MASS    = "mass"        # mass_mg stores mg; loading = mg / area
INPUT_LOADING = "loading"     # mass_mg stores mg/cm² directly

# element_cf_sources values (per-element CF source in AnalysisSheet)
CF_SOURCE_CALIBRATION = "calibration"   # use the element's CalibrationSheet CF
CF_SOURCE_SELF        = "self"          # use the sheet's own self-derived CF (mean mass_loading/xrf_total)
# Any other value is interpreted as a float (manual override)


@dataclass
class CalibrationSample:
    sample_id: str
    mass_mg: float              # raw input: mg if mode='mass', mg/cm² if mode='loading'
    xrf_loading: float          # mg/cm²
    mass_uncertainty: float = 0.01
    is_excluded: bool = False   # manually excluded from CF calculation


@dataclass
class CalibrationSheet:
    element: str
    substrate: str
    samples: list = field(default_factory=list)         # list[CalibrationSample]
    diameter_cm: Optional[float] = None                  # None → use project default
    input_mode: str = INPUT_MASS

    def effective_diameter(self, project) -> float:
        return self.diameter_cm if self.diameter_cm is not None else project.diameter_cm

    def effective_area_cm2(self, project) -> float:
        d = self.effective_diameter(project)
        return math.pi * (d / 2) ** 2

    def mass_loading_of(self, sample, project) -> float:
        if self.input_mode == INPUT_LOADING:
            return sample.mass_mg
        return sample.mass_mg / self.effective_area_cm2(project)


@dataclass
class AnalysisSample:
    sample_id: str
    mass_mg: float
    xrf_loadings: dict = field(default_factory=dict)
    notes: str = ""
    practical_specific_capacity: float = float("nan")  # measured practical SC per sample, mAh/g
    is_excluded: bool = False                          # manually excluded from calculations


@dataclass
class AnalysisSheet:
    name: str
    elements: list = field(default_factory=list)
    samples: list = field(default_factory=list)
    diameter_cm: Optional[float] = None
    input_mode: str = INPUT_MASS
    # Per-element CF source: maps element → "calibration" | "self" | str(float)
    # Missing keys default to "calibration"
    element_cf_sources: dict = field(default_factory=dict)
    # Per-element expected (theoretical) specific capacities (mAh/g); absent key = inactive
    element_specific_capacities: dict = field(default_factory=dict)

    def effective_diameter(self, project) -> float:
        return self.diameter_cm if self.diameter_cm is not None else project.diameter_cm

    def effective_area_cm2(self, project) -> float:
        d = self.effective_diameter(project)
        return math.pi * (d / 2) ** 2

    def mass_loading_of(self, sample, project) -> float:
        if self.input_mode == INPUT_LOADING:
            return sample.mass_mg
        return sample.mass_mg / self.effective_area_cm2(project)


@dataclass
class Project:
    name: str
    diameter_cm: float = 1.27
    calibration_sheets: list = field(default_factory=list)
    analysis_sheets: list = field(default_factory=list)

    @property
    def area_cm2(self) -> float:
        return math.pi * (self.diameter_cm / 2) ** 2

    def calibration_by_element(self, element: str) -> Optional["CalibrationSheet"]:
        for cs in self.calibration_sheets:
            if cs.element == element:
                return cs
        return None
