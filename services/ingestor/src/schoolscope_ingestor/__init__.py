"""SchoolScope England data ingestion service.

This package only ever reads and writes officially published, public data
(GIAS establishment extracts, DfE Explore Education Statistics releases, and
local authority catchment boundary datasets published under a reuse licence).
It never stores a user's submitted home address or any other end-user
personal data; postcode lookup for an individual user is the web app's
concern, not this service's.
"""

__version__ = "0.1.0"
