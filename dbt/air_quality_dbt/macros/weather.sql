{% macro resolve_numeric(uci_expr, om_expr) %}
case
    when {{ uci_expr }} is not null then {{ uci_expr }}
    when {{ om_expr }} is not null then {{ om_expr }}
    else null
end
{% endmacro %}

{% macro resolve_source(uci_expr, om_expr) %}
case
    when {{ uci_expr }} is not null then 'uci'
    when {{ om_expr }} is not null then 'openmeteo'
    else null
end
{% endmacro %}

{# 16-point compass, N centered on 0°. Matches UCI wd labels. #}
{% macro compass_16(deg_expr) %}
case
    when {{ deg_expr }} is null then null
    else (array['N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSW','SW','WSW','W','WNW','NW','NNW'])[
        (mod(cast(round(({{ deg_expr }}) / 22.5) as integer), 16) + 16) % 16 + 1
    ]
end
{% endmacro %}

{# Alduchov & Eskridge (1996) Magnus, ratio of saturation vapor pressure. #}
{% macro relative_humidity_pct(temp_expr, dewp_expr) %}
case
    when {{ temp_expr }} is null or {{ dewp_expr }} is null then null
    when {{ temp_expr }} <= -240 or {{ dewp_expr }} <= -240 then null
    else least(
        100.0,
        greatest(
            0.0,
            100.0 * exp(
                (17.625 * ({{ dewp_expr }})) / (({{ dewp_expr }}) + 243.04)
                - (17.625 * ({{ temp_expr }})) / (({{ temp_expr }}) + 243.04)
            )
        )
    )
end
{% endmacro %}
