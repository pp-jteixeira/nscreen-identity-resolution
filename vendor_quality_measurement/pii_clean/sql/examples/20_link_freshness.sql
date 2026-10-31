WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090
    WHERE (source = 'endato' AND metric_row_id IN (
        '174DF23ED50299325123B7660ECB3AA68FEDD02FA7345B47D575396DEAF0419A'))
       OR (source = 'haymarket' AND metric_row_id IN (
        '774416407C42EA3A688EA08521D045D280032B7973C5D95696F91DC9BB8CE731'))
       OR (source = 'medscape' AND metric_row_id IN (
        '5871A1225861F4254047C0F9F0C40D5B0E9F433B8AAA9632B36BAEACE4DCD51D',
        'ABDD5253F7AE1234C4E9B5856FF54938AD6993BA3DA4740DDF24B1DB96F480AA'))
)
SELECT m.source,
       m.email,
       m.npi,
       m.link_last_observed_day,
       m.source_latest_observed_day,
       m.source_age_days,
       m.link_lag_days,
       m.link_freshness_as_of_day AS evaluated_on
FROM selected m
ORDER BY m.source, m.metric_row_id
