-- Registration-scoped stored status, without rebuilding source observations.
SELECT DISTINCT source,email,registration_guid,npi,registration_link_status,
       registration_link_last_observed_day,registration_latest_observed_day,
       registration_superseded_since_day,registration_superseded_by_npis,
       sequence_as_of_day
FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090
WHERE source='medscape' AND email IN ('sbrooks.arnp@gmail.com','fangchenmd@gmail.com')
ORDER BY source,email,registration_guid,npi
