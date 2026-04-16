-- Team-level aggregations.

-- name: architecture_code_gap
-- Proxy = PR iteration count * post-merge churn rate.
WITH pr_iterations AS (
    SELECT
        pr.id,
        pr.author_id,
        pr.base_repo_id,
        COUNT(prc.id) AS comment_count
    FROM pull_requests pr
    LEFT JOIN pull_request_comments prc ON prc.pull_request_id = pr.id
    WHERE pr.merged_date BETWEEN :since AND :until
      {synth_filter_pr}
    GROUP BY pr.id, pr.author_id, pr.base_repo_id
),
post_merge_churn AS (
    SELECT
        pr.id AS pr_id,
        COUNT(DISTINCT c2.sha) AS post_merge_commits
    FROM pull_requests pr
    JOIN repo_commits rc1 ON rc1.repo_id = pr.base_repo_id
    JOIN commits c1 ON c1.sha = rc1.commit_sha AND c1.sha = pr.merge_commit_sha
    JOIN repo_commits rc2 ON rc2.repo_id = pr.base_repo_id
    JOIN commits c2 ON c2.sha = rc2.commit_sha
         AND c2.authored_date BETWEEN pr.merged_date AND DATE_ADD(pr.merged_date, INTERVAL 7 DAY)
    WHERE pr.merged_date BETWEEN :since AND :until
    GROUP BY pr.id
)
SELECT
    a.user_name,
    a.full_name,
    COUNT(DISTINCT i.id) AS prs,
    ROUND(AVG(i.comment_count), 2) AS mean_comments_per_pr,
    COALESCE(ROUND(AVG(p.post_merge_commits), 2), 0) AS mean_post_merge_churn,
    ROUND(
        AVG(i.comment_count) * COALESCE(AVG(p.post_merge_commits), 0) / 10.0,
        2
    ) AS acg_score
FROM pr_iterations i
JOIN accounts a ON a.id = i.author_id
LEFT JOIN post_merge_churn p ON p.pr_id = i.id
GROUP BY a.user_name, a.full_name
ORDER BY acg_score DESC;

-- name: ai_vs_traditional
-- Compares DORA-adjacent metrics across engineers grouped by AI signal strength.
-- Signal bands derived from mean commit size:
--   high   : > 300 LoC avg
--   mixed  : 120-300
--   low    : < 120
WITH per_author AS (
    SELECT
        c.author_id,
        COUNT(*) AS commits,
        AVG(c.additions + c.deletions) AS mean_diff,
        AVG(TIMESTAMPDIFF(HOUR, pr.created_date, pr.merged_date)) AS cycle_hours
    FROM commits c
    LEFT JOIN pull_requests pr ON pr.author_id = c.author_id
        AND pr.merged_date BETWEEN :since AND :until
    WHERE c.authored_date BETWEEN :since AND :until
      {synth_filter_c}
    GROUP BY c.author_id
)
SELECT
    CASE
      WHEN mean_diff >= 300 THEN 'high'
      WHEN mean_diff >= 120 THEN 'mixed'
      ELSE 'low'
    END AS ai_signal_band,
    COUNT(*) AS engineers,
    ROUND(AVG(commits), 1) AS mean_commits,
    ROUND(AVG(mean_diff), 0) AS mean_diff_size,
    ROUND(AVG(cycle_hours), 1) AS mean_cycle_hours
FROM per_author
GROUP BY ai_signal_band
ORDER BY FIELD(ai_signal_band, 'high', 'mixed', 'low');
