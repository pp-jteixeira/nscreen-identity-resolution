WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090
    WHERE (source = 'endato' AND metric_row_id IN (
        '174DF23ED50299325123B7660ECB3AA68FEDD02FA7345B47D575396DEAF0419A'))
       OR (source = 'healthlink' AND metric_row_id IN (
        '39C2F78FA687F1D8257987C722B350B90A42B9D83BDCB5B4C32B9E8D2EC80905'))
       OR (source = 'medscape' AND metric_row_id IN (
        '1D343DCA154DC149F0A4E90D7B8561D297C4AECDD3C3E710080DF56062E864CE'))
)
SELECT m.source,
       m.email,
       m.npi,
       m.observation_count,
       m.observed_day_count,
       m.first_seen_day,
       m.last_seen_day,
       m.undated_observation_count
FROM selected m
ORDER BY m.source, m.metric_row_id
