# Changelog

## 1.0.RC3

Third release candidate based on free-roaming play tests.

- Makes XYZ coordinates authoritative in Spatial Navigation State.
- Replaces required `current_location` semantics with optional `location_anchor` semantics.
- Keeps `active_path` and nav indexes optional so off-path movement remains valid.
- Adds configurable query radii, result limits and location/path tolerances.
- Generates a sparse runtime candidate index during compilation.
- Resolves polygon and multipolygon area membership from the current coordinate.
- Finds nearby discovered locations dynamically; `nearby_ids` is deprecated.
- Finds nearby roads and waterways dynamically; reports on-path, alongside or nearby relation, side of sequence, nearest segment and projected cumulative distance.
- Retains detailed active-path segment, grade, flow and waypoint output when path progress is available.
- Deprecates author-maintained `area_ids`; area membership is now coordinate-derived.
- Advances the source schema to 1.2.

### RC2 migration

- Add `query_settings` to `world-geography.yaml`.
- Add `x_km`, `y_km`, `z_m` and `position_mode` to `initial_navigation`.
- Rename `current_location` to optional `location_anchor`.
- Remove `area_ids` and `nearby_ids`; the compiler and refresh script now resolve them dynamically.
- Keep `active_path` and its indexes only when movement is actually path-relative.
- Rebuild the bundle; do not mix RC2 state or PawScript with RC3.

## 1.0.RC2

Second release candidate based on initial integration testing.

- Merges the two author-facing semantic files into `world-spatial.yaml` while preserving separate Location and Area runtime trackers.
- Advances the source schema to 1.1.
- Replaces road-specific `routes` with generic typed `paths`.
- Adds `river`, `creek` and `stream` sequence semantics: nav points run upstream to downstream.
- Adds a River Vey sample path with decreasing elevation and a road/river crossing.
- Replaces `active_route` with `active_path` and the checkpoint-only navigation field with `next_waypoint_nav_index`.
- Adds active-path type, optional navigability, flow relation and generic waypoint output to Spatial Local Context.
- Adds validation for path types, path references and unexpected elevation rises along flowing-water paths.
- Adds a complete beginner world-building guide to the HTML and Markdown documentation.

### RC1 migration

- Combine the contents of `world-locations.yaml` and `world-areas.yaml` beneath `locations:` and `areas:` in `world-spatial.yaml`.
- Rename `routes` to `paths`, add a nonempty `type` to every path, and rename every `route_ids` list to `path_ids`.
- Rename `active_route` to `active_path`.
- Rename `next_checkpoint_nav_index` to `next_waypoint_nav_index`.
- Rebuild the bundle; do not mix RC1 YAML with the RC2 compiler or runtime script.

## 1.0.RC1

Initial release candidate.

- Defines metric coordinates: `x_km`, `y_km`, `z_m`.
- Separates spatial geometry, location semantics and area semantics.
- Supports location points, ordered route nav points, polygons and multipolygons.
- Defines nested and overlapping areas with authoritative `contains` relationships.
- Includes hidden source trackers and a compact AI-only local-context tracker.
- Includes embedded PawScript for location joins, nearby-place distances, area summaries, route-segment distance, elevation change and grade.
- Includes static location-state overlays and host-owned navigation state.
- Includes a reusable IW data-bank bundle template and a sample-compiled bundle.
- Includes a self-contained HTML reference and a YAML validation/bundle compiler.
- Defers arbitrary-coordinate point-in-polygon resolution and dynamic border geometry to a future release.
