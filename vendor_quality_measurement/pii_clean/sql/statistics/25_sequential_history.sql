-- One observation per source/email for sequence totals, independently of record multiplicity.
WITH records AS (SELECT * FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090), emails AS (
    SELECT source, email, max(n_versions_observed) AS versions, max(n_swaps) AS swaps, max(n_flipbacks) AS flipbacks,
           bool_or(stability_history_sufficient) AS sufficient, bool_or(sequence_has_undated_observations) AS undated
    FROM records GROUP BY source, email
)
SELECT source, count(*) AS emails, count_if(versions IS NOT NULL) AS dated_emails,
       count_if(versions IS NULL) AS undated_emails, count_if(sufficient) AS sufficient_history_emails,
       count_if(swaps > 0) AS emails_with_swaps, count_if(flipbacks > 0) AS emails_with_flipbacks,
       100e0 * count_if(swaps > 0) / nullif(count_if(versions IS NOT NULL), 0) AS swap_pct_of_dated_emails,
       100e0 * count_if(flipbacks > 0) / nullif(count_if(versions IS NOT NULL), 0) AS flipback_pct_of_dated_emails,
       count_if(undated) AS emails_with_incomplete_dates
FROM emails GROUP BY source
