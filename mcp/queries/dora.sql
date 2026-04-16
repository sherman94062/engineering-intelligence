-- DORA metric queries.
-- Named snippets are selected with db.load_sql("dora.sql", key="...").
-- `{synth_filter}` is a trusted server-side fragment (see db.synth_filter).

-- name: deployment_frequency
SELECT
    DATE_FORMAT(p.finished_date, '%Y-%m-%d') AS day,
    r.name AS repo,
    COUNT(*) AS deploys
FROM cicd_pipelines p
JOIN cicd_pipeline_commits pc ON pc.pipeline_id = p.id
JOIN repos r ON r.id = pc.repo_id
WHERE p.type = 'DEPLOYMENT'
  AND p.result = 'SUCCESS'
  AND p.finished_date BETWEEN :since AND :until
  {synth_filter}
GROUP BY day, r.name
ORDER BY day, repo;

-- name: lead_time_for_changes
SELECT
    r.name AS repo,
    COUNT(*) AS deploys,
    ROUND(AVG(TIMESTAMPDIFF(MINUTE, c.authored_date, p.finished_date)) / 60, 2) AS mean_hours,
    ROUND(
        SUBSTRING_INDEX(
            SUBSTRING_INDEX(
                GROUP_CONCAT(TIMESTAMPDIFF(MINUTE, c.authored_date, p.finished_date)
                             ORDER BY TIMESTAMPDIFF(MINUTE, c.authored_date, p.finished_date)),
                ',', CEIL(0.5 * COUNT(*))
            ),
            ',', -1
        ) / 60.0,
        2
    ) AS median_hours
FROM cicd_pipelines p
JOIN cicd_pipeline_commits pc ON pc.pipeline_id = p.id
JOIN repos r ON r.id = pc.repo_id
JOIN commits c ON c.sha = pc.commit_sha
WHERE p.type = 'DEPLOYMENT'
  AND p.result = 'SUCCESS'
  AND p.finished_date BETWEEN :since AND :until
  {synth_filter}
GROUP BY r.name
ORDER BY mean_hours;

-- name: change_failure_rate
WITH deploys AS (
    SELECT
        p.id AS pipeline_id,
        p.finished_date,
        pc.repo_id
    FROM cicd_pipelines p
    JOIN cicd_pipeline_commits pc ON pc.pipeline_id = p.id
    WHERE p.type = 'DEPLOYMENT'
      AND p.finished_date BETWEEN :since AND :until
      {synth_filter}
),
failures AS (
    SELECT DISTINCT d.pipeline_id
    FROM deploys d
    JOIN issues i ON i.type = 'INCIDENT'
       AND i.created_date BETWEEN d.finished_date AND DATE_ADD(d.finished_date, INTERVAL 24 HOUR)
)
SELECT
    r.name AS repo,
    COUNT(d.pipeline_id) AS deploys,
    COUNT(f.pipeline_id) AS failed_deploys,
    ROUND(100.0 * COUNT(f.pipeline_id) / NULLIF(COUNT(d.pipeline_id), 0), 2) AS cfr_pct
FROM deploys d
LEFT JOIN failures f ON f.pipeline_id = d.pipeline_id
JOIN repos r ON r.id = d.repo_id
GROUP BY r.name
ORDER BY cfr_pct DESC;

-- name: time_to_restore
SELECT
    COUNT(*) AS incidents,
    ROUND(AVG(lead_time_minutes) / 60.0, 2) AS mean_hours,
    ROUND(MIN(lead_time_minutes) / 60.0, 2) AS min_hours,
    ROUND(MAX(lead_time_minutes) / 60.0, 2) AS max_hours
FROM issues
WHERE type = 'INCIDENT'
  AND resolution_date IS NOT NULL
  AND created_date BETWEEN :since AND :until
  {synth_filter};

-- name: performance_level
-- Combines DF / LT / CFR / TTR into a Google-DORA band per repo.
WITH df AS (
    SELECT pc.repo_id, COUNT(*) AS deploys
    FROM cicd_pipelines p
    JOIN cicd_pipeline_commits pc ON pc.pipeline_id = p.id
    WHERE p.type = 'DEPLOYMENT'
      AND p.result = 'SUCCESS'
      AND p.finished_date BETWEEN :since AND :until
      {synth_filter}
    GROUP BY pc.repo_id
),
lt AS (
    SELECT pc.repo_id,
           AVG(TIMESTAMPDIFF(MINUTE, c.authored_date, p.finished_date)) / 60.0 AS mean_hours
    FROM cicd_pipelines p
    JOIN cicd_pipeline_commits pc ON pc.pipeline_id = p.id
    JOIN commits c ON c.sha = pc.commit_sha
    WHERE p.type = 'DEPLOYMENT'
      AND p.result = 'SUCCESS'
      AND p.finished_date BETWEEN :since AND :until
      {synth_filter}
    GROUP BY pc.repo_id
)
SELECT
    r.name AS repo,
    COALESCE(df.deploys, 0) AS deploys_in_window,
    ROUND(lt.mean_hours, 2) AS lead_time_hours
FROM repos r
LEFT JOIN df ON df.repo_id = r.id
LEFT JOIN lt ON lt.repo_id = r.id
ORDER BY deploys_in_window DESC;

-- name: trend
SELECT
    DATE_FORMAT(p.finished_date, '%x-W%v') AS iso_week,
    COUNT(*) AS deploys,
    ROUND(AVG(CASE WHEN p.result = 'SUCCESS' THEN 1 ELSE 0 END) * 100, 2) AS success_pct
FROM cicd_pipelines p
WHERE p.type = 'DEPLOYMENT'
  AND p.finished_date BETWEEN :since AND :until
  {synth_filter_alias}
GROUP BY iso_week
ORDER BY iso_week;
