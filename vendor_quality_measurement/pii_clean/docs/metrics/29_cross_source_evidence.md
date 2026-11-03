# Cross-source evidence

**Status:** implemented, stored and measured.

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

## Real examples: contrasting outcomes

Executed November 3, 2026 against `iceberg.jteixeira_ipa.pii_clean` (snapshot `985110448175465479`) for source `healthlink`. Each case is the first link by `link_id` that has the pattern; these selected cases explain outcomes and do not measure prevalence. The other sources' rows for the same emails come from the same table.

```sql
SELECT source, email, npi, source_state_values, transform(source_name_values, n -> n.first_name || ' ' || n.last_name) AS names,
       xsrc_npi_agree_sources, xsrc_npi_disagree_sources, xsrc_state_agree_sources, xsrc_state_disagree_sources,
       xsrc_name_agree_sources, xsrc_name_disagree_sources
FROM iceberg.jteixeira_ipa.pii_clean
WHERE source = 'healthlink' AND link_id IN ('00003442C08B2FCBE1EABC1935D259AF8216042798A787285C15115A84128097', '0000734A2570E79F4EA5699809A46672FA8C95FCF021875C8A269185CB474986', '00001EF89629AF32381104681E444ECECAE295B4E6465FA2FEE8CEA2A4D348AA', '00006002C8B151910CB639620097E29E13905A5F998BA53643739E073599B47F', '0000451A3A0AF5AD34C79DB8D44604607C2A70A559485213973C215631CCF00E')
ORDER BY link_id
```

| HealthLink link | NPI agree | NPI disagree | State agree / disagree | Name agree / disagree | What it shows |
|---|---|---|---|---|---|
| dwermuth@wi.rr.com, 1871585505, WI, DOUGLAS WERMUTH | DRDB, Haymarket, Medscape, QuantumMedica | none | DRDB, Medscape / none | DRDB, Haymarket, Medscape / none | Four sources report the same email and NPI, and every comparable state and name agrees. |
| melbecker777@gmail.com, 1891942769, MI, MELISSA BECKER | none | Haymarket, Medscape | none | none | Haymarket and Medscape both report NPI 1780950329 for this email with the same name. HealthLink stands alone, so the NPI itself is in doubt. |
| sungchoemd@yahoo.com, 1164551925, MO, SUNG CHOE | Haymarket | Endato, Medscape | none | none | Haymarket agrees but supplies no state or name, so nothing more can be compared. Endato and Medscape report NPI 1689752446 in CA for the same email. |
| tara.perkins@earthlink.net, 1306093034, OH, TARA PERKINS | Haymarket, Medscape | QuantumMedica | none / Medscape | Haymarket, Medscape / none | Medscape reports the same NPI and name but state FL against OH. QuantumMedica reports another NPI, 1477658458, without state or name. |
| erin_bryn@yahoo.com, 1215659008, MN, ERIN ONYANGO | Medscape | none | Medscape / none | none / Medscape | Medscape reports the same NPI and state with the name ERIN SCHEDTLER, as one person under two surnames. |

## Statistics by source

Measured **November 3, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `985110448175465479`, reading the stored `xsrc_` columns. Exact population counts. Links are the source/email/NPI links of the source and percentages use them unless a column says otherwise.

[Statistics SQL 1](../../sql/statistics/29_cross_source_evidence.sql) supplies the first two tables and [statistics SQL 2](../../sql/statistics/29_cross_source_evidence_statement_002.sql) the third.

| Source | Links | Email also in another source | Another source agrees on the NPI | Others report only different NPIs | Agree, and others report more NPIs |
|---|---:|---:|---:|---:|---:|
| DRDB | 826,886 | 490,357 (59.3%) | 440,235 (53.2%) | 50,122 (6.1%) | 37,738 (4.6%) |
| Endato | 5,427,459 | 958,417 (17.7%) | 823,628 (15.2%) | 134,789 (2.5%) | 26,979 (0.5%) |
| Haymarket | 4,223,245 | 2,211,410 (52.4%) | 2,095,134 (49.6%) | 116,276 (2.8%) | 83,983 (2.0%) |
| HealthLink | 7,688,451 | 1,973,429 (25.7%) | 1,831,825 (23.8%) | 141,604 (1.8%) | 74,288 (1.0%) |
| Medscape | 3,662,055 | 1,789,088 (48.9%) | 1,656,730 (45.2%) | 132,358 (3.6%) | 75,402 (2.1%) |
| QuantumMedica | 1,705,723 | 731,341 (42.9%) | 649,591 (38.1%) | 81,750 (4.8%) | 32,109 (1.9%) |
| RocketReach | 3,199,535 | 603,665 (18.9%) | 537,052 (16.8%) | 66,613 (2.1%) | 25,242 (0.8%) |

State and name are compared only on links where another source agrees on the NPI. Percentages for state and name use the comparable links of the same row. A link can have both an agreeing and a disagreeing source, because different sources can differ.

| Source | Links with an NPI-agreeing source | State comparable, n (%) | State agree, n (%) | State disagree, n (%) | Name comparable, n (%) | Name agree, n (%) | Name disagree, n (%) |
|---|---:|---:|---:|---:|---:|---:|---:|
| DRDB | 440,235 | 304,705 (69.2%) | 268,359 (88.1%) | 62,977 (20.7%) | 394,893 (89.7%) | 374,919 (94.9%) | 52,898 (13.4%) |
| Endato | 823,628 | 491,827 (59.7%) | 325,720 (66.2%) | 193,493 (39.3%) | 641,959 (77.9%) | 376,644 (58.7%) | 282,639 (44.0%) |
| Haymarket | 2,095,134 | no vendor state | no vendor state | no vendor state | 1,983,740 (94.7%) | 1,815,285 (91.5%) | 307,879 (15.5%) |
| HealthLink | 1,831,825 | 1,187,506 (64.8%) | 939,718 (79.1%) | 310,167 (26.1%) | 1,786,821 (97.5%) | 1,675,352 (93.8%) | 235,550 (13.2%) |
| Medscape | 1,656,730 | 1,134,249 (68.5%) | 869,697 (76.7%) | 309,936 (27.3%) | 1,604,157 (96.8%) | 1,451,124 (90.5%) | 252,142 (15.7%) |
| QuantumMedica | 649,591 | no vendor state | no vendor state | no vendor state | no vendor name | no vendor name | no vendor name |
| RocketReach | 537,052 | 368,337 (68.6%) | 327,081 (88.8%) | 68,884 (18.7%) | 519,370 (96.7%) | 495,077 (95.3%) | 61,478 (11.8%) |

Share of each source's links on which each other source agrees on the NPI. The table is not symmetric, because each row uses its own source's links as the denominator.

| Source | DRDB | Endato | Haymarket | HealthLink | Medscape | QuantumMedica | RocketReach |
|---|---:|---:|---:|---:|---:|---:|---:|
| DRDB | — | 9.2% | 32.6% | 18.7% | 21.2% | 27.9% | 8.4% |
| Endato | 1.4% | — | 6.7% | 5.1% | 4.4% | 4.6% | 3.1% |
| Haymarket | 6.4% | 8.6% | — | 27.3% | 25.1% | 7.3% | 5.6% |
| HealthLink | 2.0% | 3.6% | 15.0% | — | 12.1% | 2.6% | 2.8% |
| Medscape | 4.8% | 6.6% | 28.9% | 25.4% | — | 4.9% | 5.7% |
| QuantumMedica | 13.5% | 14.7% | 18.2% | 11.7% | 10.6% | — | 4.6% |
| RocketReach | 2.2% | 5.2% | 7.4% | 6.7% | 6.6% | 2.5% | — |

**Interpretation:** between 15% and 53% of the links of a source have another vendor agreeing on the NPI, and between 1.8% and 6.1% have other vendors reporting only different NPIs. When sources agree on the NPI their states and names mostly agree too: among comparable links, state agreement is 66% to 89% and name agreement 59% to 95%. Endato disagrees most (39% state, 44% name), so its states and names are the least consistent with the other vendors. QuantumMedica reports no state and almost no name, and Haymarket reports no state, so neither can be checked on those. The pair table shows how much sources overlap. Haymarket shares the NPI on 27% of its links with HealthLink and 25% with Medscape, while Endato and RocketReach overlap little with anyone, mostly because other sources do not hold their emails. Agreement shows that vendors report the same pair, and it cannot show that the pair is correct: vendors share lineage with each other and with directories, so two agreeing sources may be one origin counted twice. The arrays name the sources so that later scoring can discount pairs that share lineage. Coverage alone implies no weight.
