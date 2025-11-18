"""
Database Schemas for PC Builder Simulator

Each Pydantic model maps to a MongoDB collection (lowercased class name).
"""
from typing import Optional, List, Dict
from pydantic import BaseModel, Field

class Component(BaseModel):
    """
    PC components catalog
    Collection: "component"
    """
    name: str = Field(..., description="Display name of the component")
    type: str = Field(..., description="Category: CPU, GPU, Motherboard, RAM, Storage, PSU, Case, Cooler")
    brand: Optional[str] = Field(None, description="Manufacturer or brand")
    price: float = Field(..., ge=0, description="Price in USD")

    # Common technical attributes (optional, used for compatibility rules)
    socket: Optional[str] = Field(None, description="CPU/Motherboard socket")
    chipset: Optional[str] = Field(None, description="Motherboard chipset")
    ram_type: Optional[str] = Field(None, description="DDR4, DDR5, etc.")
    ram_speed: Optional[int] = Field(None, description="Max supported RAM speed in MT/s")
    ram_slots: Optional[int] = Field(None, description="Number of RAM slots on motherboard")

    tdp: Optional[int] = Field(None, description="Thermal Design Power (W)")
    psu_wattage: Optional[int] = Field(None, description="Power Supply wattage")

    form_factor: Optional[str] = Field(None, description="ATX, mATX, ITX")
    case_gpu_max_length_mm: Optional[int] = Field(None, description="Max GPU length that case supports in mm")
    case_cooler_max_height_mm: Optional[int] = Field(None, description="Max CPU cooler height in mm")
    psu_type: Optional[str] = Field(None, description="ATX, SFX, etc.")

    gpu_length_mm: Optional[int] = Field(None, description="GPU length in mm")

    storage_interfaces: Optional[List[str]] = Field(default=None, description="List of supported storage interfaces, e.g., ['SATA', 'M.2']")
    m2_slots: Optional[int] = Field(None, description="Number of M.2 slots on motherboard")
    sata_ports: Optional[int] = Field(None, description="Number of SATA ports on motherboard")

    cooler_tdp_rating: Optional[int] = Field(None, description="Max TDP that cooler can handle")
    cooler_height_mm: Optional[int] = Field(None, description="Cooler height in mm")

class Build(BaseModel):
    """
    User builds (saved configurations)
    Collection: "build"
    """
    name: str = Field(..., description="Name of the build")
    selections: Dict[str, str] = Field(
        ..., description="Mapping of component type to component _id string. e.g., {'CPU': '...', 'GPU': '...'}"
    )
    total_price: float = Field(..., ge=0)
    estimated_power_w: int = Field(..., ge=0)
    is_valid: bool = Field(...)
    issues: List[str] = Field(default_factory=list)
