# Privacy

## What this application stores

SchoolScope England stores aggregate, institution-level public data only:
schools, trusts, local authorities, published statistics, and officially
published catchment/admissions boundaries. It does not store pupil-level
data of any kind.

## What this application does not store

- **Home addresses or coordinates.** A user's clicked map point or typed
  address is used in-memory for a single request to compute a catchment
  result and is never written to the database.
- **Submitted postcodes tied to identity.** `PostcodeCache` stores only a
  normalised postcode, its centroid coordinates, and a source/expiry, exactly
  like a public postcode lookup API's own cache would. There is no user
  identifier column anywhere in that table, and nothing links a cached
  postcode back to a session, IP address, or account.
- **Postcodes in analytics.** No analytics event, log line, or error report
  in this codebase includes a submitted postcode or coordinate value. If you
  add analytics instrumentation, this rule applies to it too.
- **Accounts, in the MVP.** There is no user authentication system; nothing
  here requires creating one to use the application's public features.

## Logging

Server logs are structured JSON with a request ID. They deliberately exclude
request bodies for the `/api/catchments/check-point` endpoint beyond a
coarse, rounded location bucket sufficient for rate-limiting and abuse
detection, never the precise submitted coordinate or postcode string.

## Database credentials

Three privilege tiers exist (`school_migrator`, `school_ingestor`,
`school_app`); see `docs/database.md`. The browser never receives a database
connection string in any form. `/status` reports database connectivity as a
boolean plus latest import timestamps, never a hostname, username, or raw
error.

## Third-party data processors

- **postcodes.io** (or whichever provider `POSTCODE_GEOCODER` is configured
  to) receives the postcode a user enters, exactly as any postcode lookup
  service would. Review that provider's own privacy policy if you change the
  default.
- No advertising or cross-site tracking script is included in this project.
