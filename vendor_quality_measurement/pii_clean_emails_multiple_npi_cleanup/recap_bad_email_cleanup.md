# Cleaning bad emails in our healthcare contact data: recap

*Data from 2026-09-28 to 2026-10-06 (9 days). Full detail is in the notebook `pii_email_npi_density_measurement.ipynb`.*

## The short version

- Some emails in our contact data belong to several different healthcare professionals. They are shared inboxes, generic company addresses or wrong data. We call them **bad emails**.
- They are rare: about **101,000 of 26.7 million emails (0.4%)**, and most of them come from two data sources, **endato** and **rocketreach**.
- Removing them would cost almost nothing in advertising: about **6,000 impressions and $88 per day (0.01%)** of the traffic that carries a matchid, roughly **$2.6K per month**. The result is the same on each of the 9 days we checked.

## 1. What problem are we solving?

Each healthcare professional has a unique ID (an NPI). A good email points to one person, so it should have one NPI. When an email points to several NPIs, it may link unrelated people together, and that hurts the quality of the audiences we build from it.

## 2. How we decide an email is bad

We counted how many different people (NPIs) each email is tied to, for each data source.

An email is **bad** if either is true:
- it is tied to **3 or more** people, or
- it is tied to **exactly 2** people with **different names**.

Two NPIs with the same name is usually one person with a duplicate record, so we keep those.

Before this, we had already dropped records whose name does not match the NPI registry, and obvious test data.

Examples of what we found: one email tied to 2,077 different people, and generic addresses such as `hosting@...`, `privacy@...` and `domainsbilling@...`.

## 3. Which sources are dirty?

| Source | Emails | Bad emails | Share bad |
|---|---|---|---|
| endato | 5.06M | 80,319 | **1.59%** |
| rocketreach | 2.92M | 18,929 | **0.65%** |
| drdb | 0.76M | 1,702 | 0.23% |
| medscape | 2.58M | 212 | 0.008% |
| stdvendor | 11.76M | 276 | 0.002% |
| haymarket | 3.63M | 0 | 0% |

- **endato and rocketreach need the cleaning.** Nearly all of their emails with two NPIs are different people.
- **haymarket, medscape and stdvendor are clean.** Their two-NPI emails are almost always one person with a duplicate record.
- **The list is stable.** We repeated the count on each of the 9 days and got the same numbers every day (only medscape moved, from 212 to 214). The table above is for 2026-09-28.

## 4. What would we lose in advertising?

The concern was that removing emails would remove cookies, and so impressions and revenue. We linked the bad emails to the cookies that carry our ads, using the matchid (the nscreen cluster ID) attached to each impression.

Over the 9 days (2026-09-28 to 2026-10-06), for deflevel 8 impressions:

| | Impressions | Revenue |
|---|---|---|
| Total, 9 days | 923.7M | $13.66M |
| On cookies linked to a bad email | 157,248 | $2,430 |
| **Of which carry a matchid** | **55,072 (0.011%)** | **$789 (0.010%)** |

- **Same every day.** Per day, the loss on impressions with a matchid ranges from 5,200 to 7,200 impressions and from $77 to $96. No day stands out.
- **Run rate:** about **$88 per day, or roughly $2.6K per month**, for impressions with a matchid. About $270 per day ($8.1K per month) if we count everything linked to a bad email.
- About **45%** of impressions have no matchid (43% to 47% depending on the day), so cleaning emails cannot change them.
- Nearly all the affected cookies have only bad emails (97%), so this is a real loss, not an upper bound. Even so, it is tiny.
- Between 2,200 and 2,500 cookies per day are affected, almost always with a single bad email.
- About 89% of the affected cookies come from endato.

## 5. Things to keep in mind

- **Nine days.** The numbers are stable over 2026-09-28 to 2026-10-06. We have not looked at a longer period.
- **Small slice.** Only about 1.5% of the cookies in this traffic link to one of our healthcare emails, so this measures that slice, not the whole campaign traffic.
- **Not counted.** Emails that fail our basic checks (invalid format, invalid NPI, test data) are not in the bad set and are not part of this loss.

## 6. Next steps

1. Apply the rule to endato, rocketreach and drdb. Leave the other sources as they are.
2. Re-run the revenue check after the cleanup to confirm the loss stays small.
