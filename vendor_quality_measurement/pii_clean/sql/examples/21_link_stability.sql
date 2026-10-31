WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090
    WHERE (source = 'endato' AND metric_row_id IN (
        'DC0EE0243F487695065E208BC5A960451759587FB3772AA025AAB99774C9E822'))
       OR (source = 'haymarket' AND metric_row_id IN (
        '9DF2E9F9E7A4ECB5EE6C33558A69F6F91B5222D322F1CDB70BE08D0EE1FB82DC'))
       OR (source = 'healthlink' AND metric_row_id IN (
        'FFBCB6093266218722EB50FD8749ED16173B42DAB91D463CDF515A029E43C3FD'))
       OR (source = 'medscape' AND metric_row_id IN (
        '823B6E80C0F4F8F215E7B4CD725A91595A9EE54607E1B167FBCDC8FC54C43AC2'))
       OR (source = 'quantummedica' AND metric_row_id IN (
        '3E55BDBA7BCA37D1F8B9FEE233B0C71869874E3238FC9A78785DBE2DB8224C30'))
)
SELECT m.source,
       m.email,
       m.npi,
       m.email_observed_day_count AS email_days,
       m.link_observed_day_count AS link_days,
       m.link_conflict_day_count AS conflict_days,
       round(100e0 * m.link_presence_share, 2) AS presence_pct,
       round(100e0 * m.link_overlap_share, 2) AS overlap_pct,
       m.link_stability_has_undated_observations AS incomplete_dates
FROM selected m
ORDER BY m.source, m.metric_row_id
