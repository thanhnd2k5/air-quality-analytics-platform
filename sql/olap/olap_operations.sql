-- =============================================================================
-- OLAP operations on the air-quality star schema (PostgreSQL)
--   fact  : dwh.fact_air_quality_hourly        (grain = 1 station × 1 hour)
--   dims  : dwh.dim_date  (day → month → quarter → year; season parallel)
--           dwh.dim_time  (hour → day_part)
--           dwh.dim_station (station → district)
--           dwh.dim_wind_direction (direction → quadrant → regime)
--   cube  : mart.mart_olap_cube  (GROUP BY CUBE, 32 pre-computed cuboids)
--
-- Every block starts with "-- name:" so src/olap/queries.py, scripts/run_olap_checks.py
-- and notebooks/olap/olap_demo.ipynb can run them one by one. Measure: PM2.5 (µg/m³).
-- Run the whole file in psql:  \i sql/olap/olap_operations.sql
-- =============================================================================

-- name: rollup_day
-- op: ROLL-UP (mức chi tiết: ngày)
-- desc: Trạm Dongsi, tháng 12/2015 — PM2.5 trung bình theo NGÀY (điểm xuất phát).
select calendar.date_day,
       round(avg(fact.pm25_ug_m3)::numeric, 1) as pm25_avg,
       count(*) as hours
from dwh.fact_air_quality_hourly as fact
join dwh.dim_date as calendar on fact.date_key = calendar.date_key
join dwh.dim_station as station on fact.station_key = station.station_key
where station.station_name = 'Dongsi' and calendar.year = 2015 and calendar.month = 12
group by calendar.date_day
order by calendar.date_day;

-- name: rollup_month
-- op: ROLL-UP (ngày → tháng)
-- desc: Cuộn lên một mức trên chiều Thời gian: cùng trạm Dongsi, gộp theo THÁNG của năm 2015.
select calendar.year, calendar.month,
       round(avg(fact.pm25_ug_m3)::numeric, 1) as pm25_avg,
       count(*) as hours
from dwh.fact_air_quality_hourly as fact
join dwh.dim_date as calendar on fact.date_key = calendar.date_key
join dwh.dim_station as station on fact.station_key = station.station_key
where station.station_name = 'Dongsi' and calendar.year = 2015
group by calendar.year, calendar.month
order by calendar.month;

-- name: rollup_year
-- op: ROLL-UP (tháng → năm)
-- desc: Cuộn lên tiếp đến mức NĂM (toàn bộ giai đoạn) cho trạm Dongsi.
select calendar.year,
       round(avg(fact.pm25_ug_m3)::numeric, 1) as pm25_avg,
       count(*) as hours
from dwh.fact_air_quality_hourly as fact
join dwh.dim_date as calendar on fact.date_key = calendar.date_key
join dwh.dim_station as station on fact.station_key = station.station_key
where station.station_name = 'Dongsi'
group by calendar.year
order by calendar.year;

-- name: rollup_station_to_district
-- op: ROLL-UP (trạm → quận)
-- desc: Cuộn lên trên chiều Địa điểm: 12 trạm gộp thành 8 quận (năm 2016).
select station.district,
       count(distinct station.station_key) as stations,
       round(avg(fact.pm25_ug_m3)::numeric, 1) as pm25_avg,
       count(*) as hours
from dwh.fact_air_quality_hourly as fact
join dwh.dim_station as station on fact.station_key = station.station_key
join dwh.dim_date as calendar on fact.date_key = calendar.date_key
where calendar.year = 2016
group by station.district
order by pm25_avg desc;

-- name: rollup_operator
-- op: ROLL-UP (toán tử ROLLUP)
-- desc: GROUP BY ROLLUP(year, quarter, month) — tổng con mọi mức của phân cấp Thời gian trong một câu; dòng NULL là mức "ALL".
select calendar.year, calendar.quarter, calendar.month,
       grouping(calendar.year, calendar.quarter, calendar.month) as grouping_id,
       round(avg(fact.pm25_ug_m3)::numeric, 1) as pm25_avg,
       count(*) as hours
from dwh.fact_air_quality_hourly as fact
join dwh.dim_date as calendar on fact.date_key = calendar.date_key
where calendar.year = 2016
group by rollup (calendar.year, calendar.quarter, calendar.month)
order by calendar.year nulls last, calendar.quarter nulls last, calendar.month nulls last;

-- name: drilldown_year
-- op: DRILL-DOWN (mức năm)
-- desc: Bắt đầu ở mức tổng hợp: PM2.5 trung bình toàn mạng lưới theo NĂM.
select calendar.year,
       round(avg(fact.pm25_ug_m3)::numeric, 1) as pm25_avg,
       count(*) filter (where fact.pm25_ug_m3 >= 115) as exceed_hours
from dwh.fact_air_quality_hourly as fact
join dwh.dim_date as calendar on fact.date_key = calendar.date_key
group by calendar.year
order by calendar.year;

-- name: drilldown_quarter
-- op: DRILL-DOWN (năm → quý)
-- desc: Khoan xuống năm 2015 theo QUÝ — quý 4 nổi bật.
select calendar.quarter,
       round(avg(fact.pm25_ug_m3)::numeric, 1) as pm25_avg,
       count(*) filter (where fact.pm25_ug_m3 >= 115) as exceed_hours
from dwh.fact_air_quality_hourly as fact
join dwh.dim_date as calendar on fact.date_key = calendar.date_key
where calendar.year = 2015
group by calendar.quarter
order by calendar.quarter;

-- name: drilldown_month
-- op: DRILL-DOWN (quý → tháng)
-- desc: Khoan xuống quý 4/2015 theo THÁNG.
select calendar.month,
       round(avg(fact.pm25_ug_m3)::numeric, 1) as pm25_avg,
       count(*) filter (where fact.pm25_ug_m3 >= 115) as exceed_hours
from dwh.fact_air_quality_hourly as fact
join dwh.dim_date as calendar on fact.date_key = calendar.date_key
where calendar.year = 2015 and calendar.quarter = 4
group by calendar.month
order by calendar.month;

-- name: drilldown_daypart
-- op: DRILL-DOWN (tháng → buổi trong ngày, chiều Giờ)
-- desc: Khoan xuống tháng 12/2015 theo chiều thứ hai: BUỔI trong ngày (dim_time).
select tod.day_part,
       round(avg(fact.pm25_ug_m3)::numeric, 1) as pm25_avg,
       count(*) as hours
from dwh.fact_air_quality_hourly as fact
join dwh.dim_date as calendar on fact.date_key = calendar.date_key
join dwh.dim_time as tod on fact.time_key = tod.time_key
where calendar.year = 2015 and calendar.month = 12
group by tod.day_part
order by pm25_avg desc;

-- name: slice_district
-- op: SLICE
-- desc: Cắt lát chiều Địa điểm tại quận = 'Dongcheng' → khối con 2 chiều (năm × mùa).
select calendar.year, calendar.season,
       round(avg(fact.pm25_ug_m3)::numeric, 1) as pm25_avg,
       count(*) as hours
from dwh.fact_air_quality_hourly as fact
join dwh.dim_station as station on fact.station_key = station.station_key
join dwh.dim_date as calendar on fact.date_key = calendar.date_key
where station.district = 'Dongcheng'
group by calendar.year, calendar.season
order by calendar.year, calendar.season;

-- name: dice_winter_south_core
-- op: DICE
-- desc: Khối con theo 3 chiều: mùa ∈ {đông, thu} × chế độ gió = nam × quận ∈ {Dongcheng, Xicheng}.
select station.district, calendar.season, wind.wind_regime,
       round(avg(fact.pm25_ug_m3)::numeric, 1) as pm25_avg,
       round(100.0 * avg((fact.pm25_ug_m3 >= 115)::int), 1) as pct_exceed,
       count(*) as hours
from dwh.fact_air_quality_hourly as fact
join dwh.dim_station as station on fact.station_key = station.station_key
join dwh.dim_date as calendar on fact.date_key = calendar.date_key
join dwh.dim_wind_direction as wind on fact.wind_direction_key = wind.wind_direction_key
where calendar.season in ('winter', 'autumn')
  and wind.wind_regime = 'southerly'
  and station.district in ('Dongcheng', 'Xicheng')
group by station.district, calendar.season, wind.wind_regime
order by station.district, calendar.season;

-- name: dice_compare_north
-- op: DICE (đối chứng)
-- desc: Cùng khối con nhưng chế độ gió = bắc — để thấy gió nam làm PM2.5 tăng gấp nhiều lần.
select station.district, calendar.season, wind.wind_regime,
       round(avg(fact.pm25_ug_m3)::numeric, 1) as pm25_avg,
       round(100.0 * avg((fact.pm25_ug_m3 >= 115)::int), 1) as pct_exceed,
       count(*) as hours
from dwh.fact_air_quality_hourly as fact
join dwh.dim_station as station on fact.station_key = station.station_key
join dwh.dim_date as calendar on fact.date_key = calendar.date_key
join dwh.dim_wind_direction as wind on fact.wind_direction_key = wind.wind_direction_key
where calendar.season in ('winter', 'autumn')
  and wind.wind_regime = 'northerly'
  and station.district in ('Dongcheng', 'Xicheng')
group by station.district, calendar.season, wind.wind_regime
order by station.district, calendar.season;

-- name: pivot_station_month
-- op: PIVOT (xoay trục)
-- desc: Xoay trục: trạm trên hàng, tháng (năm 2016) lên cột — bảng chéo bằng FILTER.
select station.station_name,
       round(avg(fact.pm25_ug_m3) filter (where calendar.month = 1)::numeric, 0) as m01,
       round(avg(fact.pm25_ug_m3) filter (where calendar.month = 2)::numeric, 0) as m02,
       round(avg(fact.pm25_ug_m3) filter (where calendar.month = 3)::numeric, 0) as m03,
       round(avg(fact.pm25_ug_m3) filter (where calendar.month = 4)::numeric, 0) as m04,
       round(avg(fact.pm25_ug_m3) filter (where calendar.month = 5)::numeric, 0) as m05,
       round(avg(fact.pm25_ug_m3) filter (where calendar.month = 6)::numeric, 0) as m06,
       round(avg(fact.pm25_ug_m3) filter (where calendar.month = 7)::numeric, 0) as m07,
       round(avg(fact.pm25_ug_m3) filter (where calendar.month = 8)::numeric, 0) as m08,
       round(avg(fact.pm25_ug_m3) filter (where calendar.month = 9)::numeric, 0) as m09,
       round(avg(fact.pm25_ug_m3) filter (where calendar.month = 10)::numeric, 0) as m10,
       round(avg(fact.pm25_ug_m3) filter (where calendar.month = 11)::numeric, 0) as m11,
       round(avg(fact.pm25_ug_m3) filter (where calendar.month = 12)::numeric, 0) as m12
from dwh.fact_air_quality_hourly as fact
join dwh.dim_station as station on fact.station_key = station.station_key
join dwh.dim_date as calendar on fact.date_key = calendar.date_key
where calendar.year = 2016
group by station.station_name
order by station.station_name;

-- name: pivot_season_wind
-- op: PIVOT (xoay trục)
-- desc: Cùng dữ liệu, khung nhìn khác: mùa trên hàng × phần tư hướng gió trên cột (đọc từ khối đã tính trước).
select season,
       round((sum(pm25_sum) filter (where wind_quadrant = 'NE') / nullif(sum(pm25_hour_count) filter (where wind_quadrant = 'NE'), 0))::numeric, 1) as gio_dong_bac,
       round((sum(pm25_sum) filter (where wind_quadrant = 'SE') / nullif(sum(pm25_hour_count) filter (where wind_quadrant = 'SE'), 0))::numeric, 1) as gio_dong_nam,
       round((sum(pm25_sum) filter (where wind_quadrant = 'SW') / nullif(sum(pm25_hour_count) filter (where wind_quadrant = 'SW'), 0))::numeric, 1) as gio_tay_nam,
       round((sum(pm25_sum) filter (where wind_quadrant = 'NW') / nullif(sum(pm25_hour_count) filter (where wind_quadrant = 'NW'), 0))::numeric, 1) as gio_tay_bac
from mart.mart_olap_cube
where cuboid = 'season,wind_quadrant'
group by season
order by case season when 'spring' then 1 when 'summer' then 2 when 'autumn' then 3 else 4 end;

-- name: cube_operator
-- op: CUBE
-- desc: GROUP BY CUBE(season, wind_regime) — mọi tổ hợp 2 chiều + tổng con + tổng toàn bộ (2² = 4 khối con).
select coalesce(calendar.season, 'ALL') as season,
       coalesce(wind.wind_regime, 'ALL') as wind_regime,
       grouping(calendar.season, wind.wind_regime) as grouping_id,
       round(avg(fact.pm25_ug_m3)::numeric, 1) as pm25_avg,
       count(*) as hours
from dwh.fact_air_quality_hourly as fact
join dwh.dim_date as calendar on fact.date_key = calendar.date_key
join dwh.dim_wind_direction as wind on fact.wind_direction_key = wind.wind_direction_key
group by cube (calendar.season, wind.wind_regime)
order by grouping_id, season, wind_regime;

-- name: grouping_sets
-- op: GROUPING SETS
-- desc: Chỉ tính đúng 3 khối con cần cho báo cáo: theo quận, theo buổi, và tổng.
select coalesce(station.district, 'ALL') as district,
       coalesce(tod.day_part, 'ALL') as day_part,
       round(avg(fact.pm25_ug_m3)::numeric, 1) as pm25_avg,
       count(*) as hours
from dwh.fact_air_quality_hourly as fact
join dwh.dim_station as station on fact.station_key = station.station_key
join dwh.dim_time as tod on fact.time_key = tod.time_key
group by grouping sets ((station.district), (tod.day_part), ())
order by district, day_part;

-- name: cube_lookup
-- op: Trả lời từ khối đã tính trước
-- desc: Đọc thẳng khối con (year, season) trong mart_olap_cube thay vì quét 420 768 dòng fact.
select year, season,
       round((pm25_sum / nullif(pm25_hour_count, 0))::numeric, 1) as pm25_avg,
       hour_count
from mart.mart_olap_cube
where cuboid = 'year,season'
order by year, case season when 'spring' then 1 when 'summer' then 2 when 'autumn' then 3 else 4 end;

-- name: cuboid_inventory
-- op: Danh mục khối con
-- desc: 32 khối con trong mart_olap_cube và số ô của từng khối.
select grouping_id, cuboid, count(*) as cells, sum(hour_count) as hours
from mart.mart_olap_cube
group by grouping_id, cuboid
order by grouping_id;
