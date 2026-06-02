{#
  Utilise le schéma custom (+schema dans dbt_project.yml) TEL QUEL, sans préfixer
  par le schéma de la cible. Adapté ici car chaque membre a un compte Snowflake isolé
  → on écrit directement dans STAGING / FINAL sans risque de collision.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
