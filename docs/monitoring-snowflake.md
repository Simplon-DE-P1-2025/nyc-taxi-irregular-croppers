# Monitoring & coûts Snowflake (volet optionnel — thème « supervision »)

> Source : https://github.com/gsoulat/formation-data-engineer/blob/main/04-Cloud-Platforms/snowflake/09-monitoring.md
> C'est le volet « supervision et maintenance » du thème. **Optionnel** dans le brief, mais c'est
> là qu'on marque des points sur la soutenance si on a le temps. Tout passe par `SNOWFLAKE.ACCOUNT_USAGE`.

## Checklist du brief (optionnel détaillé)
- [ ] État des lieux en 3 lignes : Compute Crédits, Storage, Data Transfer
- [ ] Identifier les requêtes échouées
- [ ] Resource monitor avec notification + suspension
- [ ] Configurer des alertes
- [ ] Dashboard de monitoring via worksheet
- [ ] Actions correctives basées sur le monitoring
- [ ] Estimer les coûts globaux du projet

## Requêtes clés (ACCOUNT_USAGE)

**Top 10 requêtes les plus coûteuses (7 j) :**
```sql
SELECT QUERY_TEXT, USER_NAME, TOTAL_ELAPSED_TIME/1000 AS SECONDS, CREDITS_USED_CLOUD_SERVICES
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE START_TIME > DATEADD('day', -7, CURRENT_TIMESTAMP())
ORDER BY CREDITS_USED_CLOUD_SERVICES DESC
LIMIT 10;
```

**Tendance quotidienne des crédits (30 j) :**
```sql
SELECT DATE_TRUNC('day', START_TIME) AS DAY, SUM(CREDITS_USED_COMPUTE) AS DAILY_CREDITS
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
WHERE START_TIME > DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY DAY ORDER BY DAY;
```

**Estimation du coût du mois en cours :**
```sql
WITH credit_price AS (SELECT 3.00 AS price_per_credit)
SELECT SUM(CREDITS_USED_COMPUTE) * price_per_credit AS ESTIMATED_COST_USD
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
CROSS JOIN credit_price
WHERE START_TIME > DATE_TRUNC('month', CURRENT_DATE());
```

**Requêtes échouées :**
```sql
SELECT QUERY_ID, QUERY_TEXT, ERROR_MESSAGE, START_TIME
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE EXECUTION_STATUS = 'FAIL'
  AND START_TIME > DATEADD('day', -7, CURRENT_TIMESTAMP())
ORDER BY START_TIME DESC;
```

## Resource Monitor (notification + suspension)
```sql
CREATE OR REPLACE RESOURCE MONITOR nyc_taxi_monitor
  WITH CREDIT_QUOTA = 50
       FREQUENCY = MONTHLY
       START_TIMESTAMP = IMMEDIATELY
  TRIGGERS
    ON 50 PERCENT DO NOTIFY
    ON 75 PERCENT DO NOTIFY
    ON 90 PERCENT DO SUSPEND
    ON 100 PERCENT DO SUSPEND_IMMEDIATE;

ALTER WAREHOUSE NYC_TAXI_WH SET RESOURCE_MONITOR = nyc_taxi_monitor;
```
Seuils via UI : 50 % notif · 75 % notif+suspension future · 90 % suspension · 100 % arrêt forcé.

## Dashboard
- **Snowsight** : Worksheets → sauvegarder les requêtes ci-dessus comme widgets de dashboard.
- **Grafana** (autre option du brief) : data source Snowflake → dashboard par défaut, puis dashboard
  sur-mesure avec nos KPIs + alertes. Réf. : https://www.flexera.com/blog/finops/grafana-snowflake-integration

## Notes
- `ACCOUNT_USAGE` a une **latence** (jusqu'à ~45 min–3 h selon les vues) ; `INFORMATION_SCHEMA`
  est temps réel mais rétention limitée.
- Pour le rapport : capturer crédits consommés, storage (GB), top requêtes, taux d'échec, coût estimé.
