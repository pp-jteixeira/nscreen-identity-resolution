# Cross-source evidence

**Status:** implemented; NPI agreement measured; stored from the next publication.

**Principle:** a link is stronger when a second vendor reports the same email and NPI, and weaker when other vendors report that email only for different NPIs. This metric lists, for every link, which other sources agree or disagree on the NPI, the vendor state and the vendor name. It publishes the agreeing and disagreeing sources and no weight or score.

**Where to find it:** `xsrc_npi_agree_sources`, `xsrc_npi_disagree_sources`, `xsrc_state_agree_sources`, `xsrc_state_disagree_sources`, `xsrc_name_agree_sources`, `xsrc_name_disagree_sources`, their six `_count` columns, `xsrc_email_source_count` and `cross_source_evidence_version` in `iceberg.jteixeira_ipa.pii_clean`. One row per source/email/NPI link; key: `source`, `link_id`. Uses all versions of the link: `email`, `npi`, `source_name_values` and `source_state_values`. The fields are computed downstream of stored core by `int_cookie__metrics`, which joins each link to the stored core of every other source on the cleaned email. Stored core must therefore hold all seven sources before cookie publication.

## How it is computed

For a link, every other source that reports the same cleaned email is classified once:

- **NPI agree:** the other source reports this email with this NPI.
- **NPI disagree:** the other source reports this email but never this NPI.
- **Neither array:** the other source does not report this email. Links with an empty email or NPI are never compared, and the other source's empty NPIs are ignored.

State and name are compared only with sources that agree on the NPI, since a different NPI is expected to have a different state and name:

- **State agree:** both links have recognized vendor states and the two sets overlap. **State disagree:** both have states and the sets are disjoint.
- **Name agree:** both links have usable vendor names and at least one name pair does not disagree under the registry name rules. **Name disagree:** both have usable names and every pair disagrees.

Unknown states or names appear in neither the agree nor the disagree array. Arrays are sorted and never null. `xsrc_email_source_count` is the number of NPI agreeing plus NPI disagreeing sources. Counts equal the array cardinalities. Haymarket counts as a source like any other. The implementation is [cross_source_evidence.sql](../../macros/cross_source_evidence.sql).

## Statistics by source

Measured **November 3, 2026** from `iceberg.jteixeira_ipa.pii_clean`, recomputing NPI agreement from the published emails and NPIs. Exact population counts. Links are distinct source/email/NPI links; percentages use the links of the source.

[Statistics SQL](../../sql/statistics/29_cross_source_evidence.sql), executed as written.

| Source | Links | Another source agrees on the NPI | Email also in another source | Others report only different NPIs | Agree, and others report more NPIs |
|---|---:|---:|---:|---:|---:|
| DRDB | 826,886 | 53.2% | 59.3% | 6.1% | 5.3% |
| Endato | 5,427,459 | 15.2% | 17.7% | 2.5% | 0.6% |
| Haymarket | 4,223,245 | 49.6% | 52.4% | 2.8% | 3.0% |
| HealthLink | 7,688,451 | 23.8% | 25.7% | 1.8% | 1.4% |
| Medscape | 3,661,537 | 45.2% | 48.9% | 3.6% | 2.3% |
| QuantumMedica | 1,705,723 | 38.1% | 42.9% | 4.8% | 2.7% |
| RocketReach | 3,199,535 | 16.8% | 18.9% | 2.1% | 1.1% |

**Interpretation:** between 15% and 53% of the links of a source have a second vendor agreeing on the NPI, while outright disagreement is uncommon at 2% to 6%. Agreement shows that vendors report the same pair, and it cannot show that the pair is correct: vendors share lineage with each other and with directories, so two agreeing sources may be one origin counted twice. The arrays name the sources so that later scoring can discount pairs that share lineage. Coverage alone implies no weight, and low agreement for Endato, RocketReach and HealthLink mostly reflects emails that no other source holds.
