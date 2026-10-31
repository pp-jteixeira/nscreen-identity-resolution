-- Registration/link counts differ from record counts and from email/NPI link counts.
WITH records AS (SELECT * FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090), links AS (
    SELECT DISTINCT source, email, registration_guid, npi, registration_link_status
    FROM records WHERE source = 'medscape'
)
SELECT source, registration_link_status, count(*) AS registration_links,
       100e0 * count(*) / sum(count(*)) OVER (PARTITION BY source) AS pct_of_registration_links
FROM links GROUP BY source, registration_link_status
