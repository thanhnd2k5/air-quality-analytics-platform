# EDGAR HTAP v3 – Data Inspection Report

**Generated:** 2026-10-19 17:08:46 UTC  
**Dataset File:** `edgar_HTAPv3_2015_PM2.5.nc`  
**File Size:** 4,976,705,030 bytes (4.635 GB)  
**Data Status:** READABLE, VALID, NO CORRUPTION DETECTED  

---

## 1. Executive Summary & Verification Highlights

- **Pollutant:** Primary Fine Particulate Matter (`PM2.5`), confirmed from variable definitions and filenames.
- **Temporal Coverage:** Exactly **1 year (2015)**, composed of **12 monthly mid-point timestamps** (`2015-01-15` to `2015-12-15`).
- **Data Type:** **Monthly Emissions** (`units: ton/month`). It is **NOT** Emission Fluxes (`kg/m²/s`), and **NOT** Annual Emissions.
- **Grid Structure:** Global regular latitude-longitude grid at **0.1° × 0.1° resolution**.
  - Latitude: 1,800 cell centers from `-89.95°` to `+89.95°` (strictly increasing).
  - Longitude: 3,600 cell centers from `-179.95°` to `+179.95°` (strictly increasing).
- **Sectors Available:** **16 standard HTAP v3 sectors** packed within a single NetCDF file.
- **Target Sectors Identified:**
  - `HTAPv3_5_1_Road_Transport` → `road_emission`
  - `HTAPv3_5_2_Brake_and_Tyre_wear` → `brake_tyre_emission`
  - `HTAPv3_4_1_Industry` → `industry_emission`
  - `HTAPv3_6_Residential` → `residential_emission`
  - `HTAPv3_3_Energy` → `energy_emission`
- **Physical Units Compatibility:** All 16 variables share the exact same unit `ton/month`. Summing `road_emission + brake_tyre_emission` to produce `traffic_emission` is mathematically and physically valid.

---

## 2. Technical Inspection Details

### A. Dimensions and Coordinates

| Dimension / Coordinate | Length / Range | Step | Direction | Type |
|---|---|---|---|---|
| `lat` | 1800 points: [-89.95, 89.95] | 0.1° | Ascending | `float64` |
| `lon` | 3600 points: [-179.95, 179.95] | 0.1° | Ascending | `float64` |
| `time` | 12 slices: [2015-01-15, 2015-12-15] | Monthly | Ascending | `datetime64[ns]` |

### B. All Available Data Variables (16 Sectors)

| Sector Code | Variable Name | Long Name | Units | Dtype | Shape |
|---|---|---|---|---|---|
| `1` | `HTAPv3_1_International_Shipping` | International Shipping | `ton/month` | `float32` | `[12, 1800, 3600]` |
| `2` | `HTAPv3_2_1_Domestic_Aviation` | Domestic Aviation | `ton/month` | `float32` | `[12, 1800, 3600]` |
| `2` | `HTAPv3_2_2_International_Aviation` | International Aviation | `ton/month` | `float32` | `[12, 1800, 3600]` |
| `3` | `HTAPv3_3_Energy` | Energy | `ton/month` | `float32` | `[12, 1800, 3600]` |
| `4` | `HTAPv3_4_1_Industry` | Industry | `ton/month` | `float32` | `[12, 1800, 3600]` |
| `4` | `HTAPv3_4_2_Fugitive` | Fugitive | `ton/month` | `float32` | `[12, 1800, 3600]` |
| `4` | `HTAPv3_4_3_Solvents` | Solvents | `ton/month` | `float32` | `[12, 1800, 3600]` |
| `5` | `HTAPv3_5_1_Road_Transport` | Road Transport | `ton/month` | `float32` | `[12, 1800, 3600]` |
| `5` | `HTAPv3_5_2_Brake_and_Tyre_wear` | Brake and Tyre wear | `ton/month` | `float32` | `[12, 1800, 3600]` |
| `5` | `HTAPv3_5_3_Domestic_shipping` | Domestic shipping | `ton/month` | `float32` | `[12, 1800, 3600]` |
| `5` | `HTAPv3_5_4_Other_ground_transport` | Other ground transport | `ton/month` | `float32` | `[12, 1800, 3600]` |
| `6` | `HTAPv3_6_Residential` | Residential | `ton/month` | `float32` | `[12, 1800, 3600]` |
| `7` | `HTAPv3_7_Waste` | Waste | `ton/month` | `float32` | `[12, 1800, 3600]` |
| `8` | `HTAPv3_8_1_Agricultural_waste_burning` | Agricultural waste burning | `ton/month` | `float32` | `[12, 1800, 3600]` |
| `8` | `HTAPv3_8_2_Agriculture_livestock` | Agriculture livestock | `ton/month` | `float32` | `[12, 1800, 3600]` |
| `8` | `HTAPv3_8_3_Agriculture_crops` | Agriculture crops | `ton/month` | `float32` | `[12, 1800, 3600]` |

---

## 3. Physical Units & Area Distortion Analysis

> [!IMPORTANT]
> **Unit Distinction: `ton/month` vs `kg/m²/s`**
> In atmospheric emissions inventories, **Monthly Emissions** (`ton/month` or `Mg/month`) represent the total mass emitted across the entire surface of the grid cell over that calendar month.
> In contrast, **Emission Flux** (`kg/m²/s`) measures the mass emitted per unit surface area per second.

### Grid Cell Physical Area at Beijing Latitude
On an equirectangular grid with cell size $\Delta \phi = 0.1^\circ, \Delta \lambda = 0.1^\circ$:
- $\Delta \text{lat} \approx 111.13 \text{ km}$ per degree $\rightarrow 0.1^\circ \approx 11.11 \text{ km}$.
- $\Delta \text{lon} \approx 111.13 \times \cos(\text{lat}) \text{ km}$. At Beijing ($\\sim 40.0^\circ \text{N}$), $\cos(40.0^\circ) \approx 0.7660 \rightarrow 0.1^\circ \approx 8.51 \text{ km}$.
- **Effective cell surface area at Beijing:** $\approx 11.11 \times 8.51 \approx 94.55 \text{ km}^2$.

Because all 12 UCI stations are situated between $39.878^\circ \text{N}$ and $40.328^\circ \text{N}$ (a span of only $\\sim 0.45^\circ$ latitude), the cell area variation across stations is under **0.8%**. However, compared to equatorial regions ($\\sim 123.5 \text{ km}^2$), Beijing grid cells are approximately $23.4\%$ smaller in physical area.

---

## 4. Station to Grid Mapping & Resolution Limits

### Bounding Box Verification
- **Proposed Bounding Box:** North `40.6`, South `39.5`, West `115.8`, East `117.0`.
- **Actual 12 Stations Envelope:** Latitude `[39.878, 40.328]`, Longitude `[116.184, 116.655]`.
- **Verification:** All 12 stations fall comfortably inside the proposed box with margins of ~0.3° to 0.4° in all directions.

### Station Mapping Table (0.1° Nearest Grid Cell)

| Station | Station Lat/Lon | EDGAR Grid Center | Grid Cell ID | Distance (km) | Shared Cell With |
|---|---|---|---|---|---|
| **Aotizhongxin** | (39.982, 116.397) | (39.95, 116.35) | `lat_39.95_lon_116.35` | 5.348 km | Aotizhongxin, Guanyuan |
| **Changping** | (40.217, 116.23) | (40.25, 116.25) | `lat_40.25_lon_116.25` | 4.036 km | Changping, Dingling |
| **Dingling** | (40.292, 116.22) | (40.25, 116.25) | `lat_40.25_lon_116.25` | 5.309 km | Changping, Dingling |
| **Dongsi** | (39.929, 116.417) | (39.95, 116.45) | `lat_39.95_lon_116.45` | 3.65 km | Dongsi, Nongzhanguan |
| **Guanyuan** | (39.929, 116.339) | (39.95, 116.35) | `lat_39.95_lon_116.35` | 2.512 km | Aotizhongxin, Guanyuan |
| **Gucheng** | (39.914, 116.184) | (39.95, 116.15) | `lat_39.95_lon_116.15` | 4.934 km | Gucheng |
| **Huairou** | (40.328, 116.628) | (40.35, 116.65) | `lat_40.35_lon_116.65` | 3.071 km | Huairou |
| **Nongzhanguan** | (39.937, 116.461) | (39.95, 116.45) | `lat_39.95_lon_116.45` | 1.72 km | Dongsi, Nongzhanguan |
| **Shunyi** | (40.127, 116.655) | (40.15, 116.65) | `lat_40.15_lon_116.65` | 2.588 km | Shunyi |
| **Tiantan** | (39.886, 116.407) | (39.85, 116.45) | `lat_39.85_lon_116.45` | 5.42 km | Tiantan |
| **Wanliu** | (39.987, 116.287) | (39.95, 116.25) | `lat_39.95_lon_116.25` | 5.174 km | Wanliu |
| **Wanshouxigong** | (39.878, 116.352) | (39.85, 116.35) | `lat_39.85_lon_116.35` | 3.113 km | Wanshouxigong |

> [!WARNING]
> **Spatial Resolution Limit: 12 stations map into only 9 unique grid cells!**
> Exactly 6 stations share 3 grid cells in pairs:
> 1. `lat_39.95_lon_116.35`: **Aotizhongxin** and **Guanyuan** (7.7 km apart) receive identical EDGAR values.
> 2. `lat_39.95_lon_116.45`: **Dongsi** and **Nongzhanguan** (3.8 km apart) receive identical EDGAR values.
> 3. `lat_40.25_lon_116.25`: **Changping** and **Dingling** (8.4 km apart) receive identical EDGAR values.

Furthermore, central urban cells in EDGAR share identical proxy downscaling values across adjacent cells for Road and Residential emissions.
