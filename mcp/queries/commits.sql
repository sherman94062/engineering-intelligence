-- Commit activity.

-- name: commit_frequency
SELECT
    DATE_FORMAT(c.authored_date, '%x-W%v') AS iso_week,
    r.name AS repo,
    c.author_name AS author,
    COUNT(*) AS commits,
    SUM(c.additions) AS lines_added,
    SUM(c.deletions) AS lines_removed
FROM commits c
JOIN repo_commits rc ON rc.commit_sha = c.sha
JOIN repos r ON r.id = rc.repo_id
WHERE c.authored_date BETWEEN :since AND :until
  {synth_filter_alias}
GROUP BY iso_week, r.name, c.author_name
ORDER BY iso_week, r.name, commits DESC;

-- name: ai_signal
-- Proxy for AI-assisted commits: large diffs authored close in time.
SELECT
    c.author_name,
    r.name AS repo,
    COUNT(*) AS batch_commits,
    ROUND(AVG(c.additions + c.deletions), 0) AS mean_diff_size,
    MAX(c.additions + c.deletions) AS max_diff_size
FROM commits c
JOIN repo_commits rc ON rc.commit_sha = c.sha
JOIN repos r ON r.id = rc.repo_id
WHERE c.authored_date BETWEEN :since AND :until
  AND (c.additions + c.deletions) > :min_batch_lines
  {synth_filter_alias}
GROUP BY c.author_name, r.name
HAVING batch_commits >= :min_batch_count
ORDER BY batch_commits DESC;
