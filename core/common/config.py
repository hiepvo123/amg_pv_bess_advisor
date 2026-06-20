"""
Common configurations for the PV BESS Advisor.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

@dataclass
class PathConfig:
    data_root: Path = Path("data/solarelectric_data")
    march_folder: str = "Du lieu thang 3-2025"
    april_folder: str = "Du lieu thang 4-2025"
    outputs_dir: Path = Path("outputs")
    
    @property
    def processed_dir(self) -> Path:
        return self.outputs_dir / "processed"
        
    @property
    def figures_dir(self) -> Path:
        return self.outputs_dir / "figures"
        
    @property
    def metrics_dir(self) -> Path:
        return self.outputs_dir / "metrics"
        
    @property
    def models_dir(self) -> Path:
        return self.outputs_dir / "models"

@dataclass
class PVConfig:
    pv_capacity_mw: Optional[float] = None
    temp_coeff: Optional[float] = None
    tilt_angle_deg: Optional[float] = None

@dataclass
class BESSConfig:
    bess_capacity_mwh: Optional[float] = None
    pcs_power_mw: Optional[float] = None
    soc_min: Optional[float] = None
    soc_max: Optional[float] = None
    eta_ch: Optional[float] = None
    eta_dis: Optional[float] = None

@dataclass
class EconomicConfig:
    electricity_price_vnd_per_kwh: float = 3460.0
    capex: Optional[float] = None
    opex: Optional[float] = None
    discount_rate: Optional[float] = None
    project_life: Optional[int] = None

@dataclass
class ModelConfig:
    random_state: int = 42

from dataclasses import dataclass, field

@dataclass
class AppConfig:
    paths: PathConfig = field(default_factory=PathConfig)
    pv: PVConfig = field(default_factory=PVConfig)
    bess: BESSConfig = field(default_factory=BESSConfig)
    economic: EconomicConfig = field(default_factory=EconomicConfig)
    model: ModelConfig = field(default_factory=ModelConfig)

    def create_output_dirs(self) -> None:
        """Create all necessary output directories."""
        self.paths.outputs_dir.mkdir(parents=True, exist_ok=True)
        self.paths.processed_dir.mkdir(parents=True, exist_ok=True)
        self.paths.figures_dir.mkdir(parents=True, exist_ok=True)
        self.paths.metrics_dir.mkdir(parents=True, exist_ok=True)
        self.paths.models_dir.mkdir(parents=True, exist_ok=True)
