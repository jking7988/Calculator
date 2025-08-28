# Core settings and constants for Double Oak estimator

SALES_TAX_RATE = 0.0825              # 8.25% sales tax on materials
ROLL_LENGTH_FT = 100                 # 100 ft per roll of silt fence

# Productivity
PRODUCTION_RATE_LF_PER_DAY = 3000    # Silt fence: linear feet per day (crew 4)
PRODUCTION_MIN_PER_DAY = 480         # Inlet protection: install minutes per crew-day (8h)

# Fuel
FUEL_RATE_PER_DAY = 100              # $100/day, min $100 when any work occurs

# Labor (per crew size)
LABOR_RATES = {
    2: {"per_day": 277.17, "per_week": 1663.03},
    3: {"per_day": 415.76, "per_week": 2494.55},
    4: {"per_day": 554.34, "per_week": 3326.06},   # locked crew size
    5: {"per_day": 692.93, "per_week": 4157.58},
}

LOCKED_CREW_SIZE = 4