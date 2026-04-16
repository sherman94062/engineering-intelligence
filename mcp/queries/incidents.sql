-- Incident queries feeding CFR / TTR / reliability views.

-- name: summary
SELECT
    i.issue_key,
    i.title,
    i.severity,
    i.created_date,
    i.resolution_date,
    ROUND(i.lead_time_minutes / 60.0, 2) AS ttr_hours,
    i.original_type AS archetype
FROM issues i
WHERE i.type = 'INCIDENT'
  AND i.created_date BETWEEN :since AND :until
  {synth_filter_alias}
ORDER BY i.created_date DESC;

-- name: linked_deploys
SELECT
    i.issue_key,
    i.title,
    i.severity,
    p.id AS pipeline_id,
    p.finished_date AS deployed_at,
    TIMESTAMPDIFF(MINUTE, p.finished_date, i.created_date) AS minutes_after_deploy
FROM issues i
JOIN cicd_pipelines p
  ON p.type = 'DEPLOYMENT'
 AND i.created_date BETWEEN p.finished_date AND DATE_ADD(p.finished_date, INTERVAL 24 HOUR)
WHERE i.type = 'INCIDENT'
  AND i.created_date BETWEEN :since AND :until
  {synth_filter_alias}
ORDER BY i.created_date DESC;
