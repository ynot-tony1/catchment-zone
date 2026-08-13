# Methodology

This is the source content behind the `/about/data` page. If you change the
policy described here, update both.

## Why there is no overall school score

Attainment, absence, workforce, and demographic measures answer different
questions and apply to different cohorts. Collapsing them into one number
requires choosing weights that hide a value judgement behind an apparent
fact. catchment-zone shows each measure separately, with its own
definition, academic year, cohort/denominator, and suppression status, so a
reader can weigh what matters to them rather than inherit someone else's
weighting.

## Suppression, provisional, and comparability

- **Suppressed** values are withheld by the source, typically to protect
  small cohorts from identification. A suppressed value is not a zero and is
  never displayed as one.
- **Provisional** values may be revised in a later release. The UI marks
  provisional figures as such.
- Metrics are never compared across academic years or across incompatible
  definitions without a visible warning; see `config/metric-definitions.yml`
  for the comparability note attached to each metric code.

## Postcode-centroid limitations

A postcode centroid is a single representative point for, on average, about
15 addresses in England, and can sit meaningfully far from any specific
address inside that postcode, especially in rural postcodes. Near a catchment
boundary, that gap can flip the result. See
`docs/admissions-and-catchments.md` for how we handle this
(`POSTCODE_RESULT_NEAR_BOUNDARY`).

## Why historical offers do not predict future offers

Published admission numbers, oversubscription pressure, sibling cohorts, and
even catchment boundaries themselves can all change year to year. A
furthest-distance-offered figure from a prior year describes what happened
once, under that year's specific mix of applicants and criteria. It is
background context for understanding how competitive a school has been, not
a threshold to plan around.

## Catchment coverage is partial by design

We do not fabricate coverage to manufacture the appearance of a complete
national map: every boundary shown is traced from a real published source,
verified with a comfortable containment margin, never invented or
estimated. Coverage grows one verified source at a time and still has real
gaps, including several major cities and county councils; see
`docs/data-sources.md` and `config/catchment-sources.yml` for exactly what
is covered today, and `PROJECT_STATUS.md` for the current gap list.
