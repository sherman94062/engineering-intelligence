-- Contributor-level queries.

-- name: activity
SELECT
    a.user_name,
    a.full_name,
    COUNT(DISTINCT c.sha) AS commits,
    COUNT(DISTINCT pr.id) AS pull_requests,
    SUM(c.additions) AS lines_added,
    SUM(c.deletions) AS lines_removed,
    MIN(c.authored_date) AS first_commit,
    MAX(c.authored_date) AS last_commit
FROM accounts a
LEFT JOIN commits c
  ON c.author_id = a.id
 AND c.authored_date BETWEEN :since AND :until
LEFT JOIN pull_requests pr
  ON pr.author_id = a.id
 AND pr.created_date BETWEEN :since AND :until
WHERE 1=1
  {synth_filter_a}
GROUP BY a.user_name, a.full_name
ORDER BY commits DESC;

-- name: bus_factor
-- Per repo, count unique committers weighted by commit volume.
SELECT
    r.name AS repo,
    COUNT(DISTINCT c.author_id) AS unique_contributors,
    MAX(author_contribution_pct) AS top_contributor_pct,
    ROUND(
        SUM(CASE WHEN author_rank <= 2 THEN author_contribution_pct ELSE 0 END),
        2
    ) AS top2_pct
FROM (
    SELECT
        rc.repo_id,
        c.author_id,
        100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY rc.repo_id) AS author_contribution_pct,
        RANK() OVER (PARTITION BY rc.repo_id ORDER BY COUNT(*) DESC) AS author_rank
    FROM commits c
    JOIN repo_commits rc ON rc.commit_sha = c.sha
    WHERE c.authored_date BETWEEN :since AND :until
      {synth_filter_c}
    GROUP BY rc.repo_id, c.author_id
) ranked
JOIN commits c ON c.author_id = ranked.author_id
JOIN repos r ON r.id = ranked.repo_id
GROUP BY r.name;

-- name: ai_adoption
-- Spread of AI-batch signal across engineers.
SELECT
    a.user_name,
    a.full_name,
    COUNT(*) AS batch_commits,
    ROUND(AVG(c.additions + c.deletions), 0) AS mean_batch_size
FROM commits c
JOIN accounts a ON a.id = c.author_id
WHERE c.authored_date BETWEEN :since AND :until
  AND (c.additions + c.deletions) > :min_batch_lines
  {synth_filter_c}
GROUP BY a.user_name, a.full_name
ORDER BY batch_commits DESC;
