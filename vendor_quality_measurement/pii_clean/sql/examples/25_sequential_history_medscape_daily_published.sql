-- Select one copy of each stored source/email history before unfolding days.
WITH selected AS (
    SELECT source,email,sequence_daily_evidence,
           row_number() OVER (PARTITION BY source,email ORDER BY metric_row_id) AS position
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090
    WHERE source='medscape' AND email IN ('sbrooks.arnp@gmail.com','fangchenmd@gmail.com')
)
SELECT r.source,r.email,s.observed_day,s.previous_observed_day,s.npis,
       s.added_npis,s.removed_npis,s.returned_npis,
       s.versions_observed,s.changes,s.swaps,s.flipbacks
FROM selected r
CROSS JOIN UNNEST(r.sequence_daily_evidence) AS s(observed_day,previous_observed_day,npis,added_npis,removed_npis,returned_npis,versions_observed,npis_observed,changes,swaps,flipbacks,history_sufficient)
WHERE r.position=1 AND (r.email='fangchenmd@gmail.com' OR s.observed_day IN (DATE '2025-10-29',DATE '2025-10-30'))
ORDER BY r.source,r.email,s.observed_day
