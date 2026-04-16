-- Pull-request analytics.

-- name: pr_cycle_time
SELECT
    r.name AS repo,
    COUNT(*) AS merged_prs,
    ROUND(AVG(TIMESTAMPDIFF(HOUR, pr.created_date, pr.merged_date)), 2) AS mean_hours,
    ROUND(MAX(TIMESTAMPDIFF(HOUR, pr.created_date, pr.merged_date)), 2) AS max_hours
FROM pull_requests pr
JOIN repos r ON r.id = pr.base_repo_id
WHERE pr.merged_date IS NOT NULL
  AND pr.merged_date BETWEEN :since AND :until
  {synth_filter_alias}
GROUP BY r.name
ORDER BY mean_hours;

-- name: pr_review_depth
SELECT
    r.name AS repo,
    COUNT(DISTINCT pr.id) AS prs,
    ROUND(AVG(comment_count), 2) AS mean_comments_per_pr,
    MAX(comment_count) AS max_comments
FROM pull_requests pr
JOIN repos r ON r.id = pr.base_repo_id
LEFT JOIN (
    SELECT pull_request_id, COUNT(*) AS comment_count
    FROM pull_request_comments
    GROUP BY pull_request_id
) c ON c.pull_request_id = pr.id
WHERE pr.merged_date BETWEEN :since AND :until
  {synth_filter_alias}
GROUP BY r.name
ORDER BY mean_comments_per_pr DESC;
