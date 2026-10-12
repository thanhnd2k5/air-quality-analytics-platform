from pydantic import BaseModel


class OlapAttribute(BaseModel):
    name: str
    label: str
    hierarchy: str
    members: list[str]


class OlapMeta(BaseModel):
    attributes: list[OlapAttribute]
    hierarchies: dict[str, list[str]]
    measures: dict[str, str]
    cube_attributes: list[str]


class OlapCell(BaseModel):
    row: str
    col: str
    value: float | None


class OlapResponse(BaseModel):
    rows: str
    cols: str | None
    measure: str
    measure_label: str
    filters: dict[str, list[str]]
    source: str
    cuboid: str | None
    sql: str
    elapsed_ms: float
    row_members: list[str]
    col_members: list[str]
    cells: list[OlapCell]
    row_totals: dict[str, float | None]
    col_totals: dict[str, float | None]
    grand_total: float | None
