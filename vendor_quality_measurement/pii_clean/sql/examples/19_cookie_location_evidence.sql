WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8096642935433856886
    WHERE (source = 'endato' AND metric_row_id IN (
        '24D4FC70423A14826D64416BCED92B280D096656622E292DA0EB587CDF30608C',
        '26B3927D287C100691C44DD0E22FBC1B9659860E48E9D6237424A884FF6075F5',
        '425055A3EB89C18FBC5885A9E12FD5EA08C792EE3E57CDD8EF841FAE19A203C9',
        '93A2769D124D567DC09A1DF0B73D69824C2111452E45045005E64F3AF0214D25',
        'C1ABB31A0F4C9EA4D613091E85B64872D18FD597460D8AD51138A13ECD0C202E'))
)
SELECT m.source,
       m.cookie_location_status,
       m.cookie_count AS mapped_uids,
       m.cookie_eligible_uid_days AS eligible_uid_days,
       m.cookie_primary_state_tied_count AS tied_uids,
       m.cookie_state_values AS states,
       m.source_state_values AS vendor_states,
       m.cookie_vendor_state_evidence AS vendor_evidence
FROM selected m
ORDER BY m.source, m.metric_row_id
