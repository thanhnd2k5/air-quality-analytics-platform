// Wind direction names as in dwh.dim_wind_direction (wind_direction_vi / wind_quadrant_vi).

/** 16-point compass, clockwise from north. */
export const COMPASS_VI: Record<string, string> = {
  N: 'Bắc',
  NNE: 'Bắc Đông Bắc',
  NE: 'Đông Bắc',
  ENE: 'Đông Đông Bắc',
  E: 'Đông',
  ESE: 'Đông Đông Nam',
  SE: 'Đông Nam',
  SSE: 'Nam Đông Nam',
  S: 'Nam',
  SSW: 'Nam Tây Nam',
  SW: 'Tây Nam',
  WSW: 'Tây Tây Nam',
  W: 'Tây',
  WNW: 'Tây Tây Bắc',
  NW: 'Tây Bắc',
  NNW: 'Bắc Tây Bắc',
}

/** 90° sectors. Their codes (NE, SE, SW, NW) also name four of the 16 directions. */
export const QUADRANT_VI: Record<string, string> = {
  NE: 'Đông Bắc (0–90°)',
  SE: 'Đông Nam (90–180°)',
  SW: 'Tây Nam (180–270°)',
  NW: 'Tây Bắc (270–360°)',
}

export function compassLabel(code: string) {
  return COMPASS_VI[code] ?? code
}
