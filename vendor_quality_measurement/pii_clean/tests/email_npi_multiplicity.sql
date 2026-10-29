-- Independently recompute distinct NPIs. never pool sources or expose failing emails.
WITH emails AS (
    SELECT source, email, count(DISTINCT npi) AS expected_count,
           min(email_npi_count) AS minimum_count, max(email_npi_count) AS maximum_count,
           count_if(email_npi_count IS NULL OR email_has_multiple_npis IS DISTINCT FROM (email_npi_count > 1)) AS invalid_rows
    FROM {{ ref(var('metric_model')) }}
    GROUP BY source, email
)
SELECT source, count(*) AS failing_emails
FROM emails
WHERE invalid_rows > 0 OR minimum_count <> expected_count OR maximum_count <> expected_count
GROUP BY source
