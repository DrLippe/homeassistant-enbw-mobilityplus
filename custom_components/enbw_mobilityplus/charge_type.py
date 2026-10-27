"""Conservative mapping of EnBW connector types to AC/DC."""


def normalize_charge_type(value: str | None) -> str | None:
    """Only map recognizable API values; do not guess from power or speed."""
    if not isinstance(value, str) or not value.strip():
        return None

    token = value.strip().upper().replace("-", "_").replace(" ", "_")
    ac_types = {"AC", "AC_CHARGING", "TYPE_2", "TYPE2", "TYPE_1", "TYPE1", "SCHUKO", "CEE"}
    dc_types = {"DC", "DC_CHARGING", "CCS", "CCS_1", "CCS_2", "CCS1", "CCS2", "COMBO", "COMBO_1", "COMBO_2", "CHADEMO"}
    if token in ac_types:
        return "AC"
    if token in dc_types:
        return "DC"
    return None
