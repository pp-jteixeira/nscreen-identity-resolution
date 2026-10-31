WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090
    WHERE (source = 'endato' AND metric_row_id IN (
        '301CF08DDB677315479773A9D4F728F00F664700BC7F030088C7A8BA0AF05ECF'))
       OR (source = 'healthlink' AND metric_row_id IN (
        '4E8278D37C840774C11F0182CFB16FF3C1F32F292E6769A17B6E328688FE1A26'))
       OR (source = 'quantummedica' AND metric_row_id IN (
        'CA266C53D1E739500DDF891E13D3117AF4CB7478E74A5F6F42E31D9510149D1C'))
)
SELECT m.source,
       m.email,
       m.npi,
       m.email_npi_count,
       m.observed_days,
       m.conflict_days,
       m.has_been_reassigned,
       m.has_conflict_linkage,
       cardinality(m.conflict_days) AS conflict_day_count
FROM selected m
ORDER BY m.source, m.metric_row_id
