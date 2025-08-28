import math
from .settings import (
    SALES_TAX_RATE, ROLL_LENGTH_FT,
    PRODUCTION_RATE_LF_PER_DAY, PRODUCTION_MIN_PER_DAY,
    FUEL_RATE_PER_DAY, LABOR_RATES, LOCKED_CREW_SIZE,
)

def get_labor_per_day():
    return LABOR_RATES[LOCKED_CREW_SIZE]["per_day"]

def required_footage(total_ft: int, waste_pct: int) -> int:
    return math.ceil(total_ft * (1 + (waste_pct or 0) / 100.0))

def posts_needed(required_ft: int, spacing_ft: int) -> int:
    return (math.ceil(required_ft / spacing_ft) + 1) if required_ft > 0 else 0

def rolls_needed(required_ft: int) -> int:
    return math.ceil(required_ft / ROLL_LENGTH_FT) if required_ft > 0 else 0

def job_days_silt(required_ft: int) -> int:
    return math.ceil(required_ft / PRODUCTION_RATE_LF_PER_DAY) if required_ft > 0 else 0

def job_days_inlet(total_minutes: int) -> int:
    return math.ceil(total_minutes / PRODUCTION_MIN_PER_DAY) if total_minutes > 0 else 0

def materials_breakdown(required_ft, cost_per_lf, posts_count, post_unit_cost):
    fabric_cost = required_ft * cost_per_lf
    hardware_cost = posts_count * post_unit_cost
    materials_subtotal = fabric_cost + hardware_cost
    tax = materials_subtotal * SALES_TAX_RATE
    return fabric_cost, hardware_cost, materials_subtotal, tax

def fuel_cost(days: int, any_work: bool) -> float:
    return FUEL_RATE_PER_DAY * (max(1, days) if any_work else 0)

def unit_cost_per_lf(required_ft, materials_subtotal, tax, labor_cost, fuel):
    return (materials_subtotal + tax + labor_cost + fuel) / required_ft if required_ft else 0.0

def unit_cost_per_unit(qty, materials_subtotal, tax, labor_cost, fuel):
    return (materials_subtotal + tax + labor_cost + fuel) / qty if qty else 0.0

def margin(final_price_unit, unit_cost_unit):
    return ((final_price_unit - unit_cost_unit) / final_price_unit) if final_price_unit > 0 else 0.0

def color_for_margin(m):
    return "green" if m >= 0.30 else "red"