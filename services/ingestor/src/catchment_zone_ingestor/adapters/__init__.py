"""Source adapters. Each module in this package talks to exactly one
officially documented, publicly accessible data source and turns its output
into the pydantic row models defined in catchment_zone_ingestor.models.

Every adapter only calls documented download/API endpoints. None of them
drive a browser or otherwise interact with an interactive map UI; the
catchments adapter, for example, calls the ArcGIS FeatureServer's documented
/query REST endpoint directly rather than automating the public map viewer.
"""
