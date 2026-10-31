# IW Spatial Context — Builder Contract

**Package version:** 1.0.RC3  
**Schema version:** 1.2  
**Status:** Release candidate  
**Audience:** Infinite Worlds authors, authoring AIs and integration tools

## 1. Purpose

IW Spatial Context keeps a complete spatial model in hidden, script-readable trackers and exposes only a compact local slice to the Infinite Worlds Storyteller. RC3 is coordinate-first: the player may stand at a named place, travel on a road, follow beside a river, cross a path, or roam open terrain without losing spatial context.

This is an authoring bundle, not a native partial-import format. Merge its components into a complete IW world export, remap colliding native IDs consistently, preserve the declared tracker variable names, and validate the complete destination world.

## 2. Source and runtime boundaries

| Source | Authority |
| --- | --- |
| `world-geography.yaml` | Coordinates, query settings, path geometry and polygon geometry |
| `world-spatial.yaml` | Static location descriptions and semantic area definitions |

`world-spatial.yaml` is convenient for authors, but compilation still emits separate hidden Location and Area trackers. The compiler also augments the hidden Geography tracker with:

- a sparse grid of candidate location and path IDs;
- bounding boxes for polygon and multipolygon geometry.

The index reduces runtime search work but is never exposed directly to the Storyteller. Exact distance, segment projection and polygon membership are calculated during refresh.

## 3. Coordinate convention

- `x_km`: kilometres east of the author-selected origin.
- `y_km`: kilometres north of the origin.
- `z_m`: metres above the chosen elevation datum.
- Two horizontal decimal places provide approximately 10-metre precision.

Coordinates are authoritative. A location ID or path index describes a relationship to those coordinates; it does not replace them.

## 4. Query settings

```yaml
query_settings:
  index_cell_km: 10.0
  nearby_location_radius_km: 15.0
  nearby_path_radius_km: 2.0
  on_path_tolerance_km: 0.05
  max_nearby_locations: 5
  max_nearby_paths: 3
  location_anchor_tolerance_km: 0.10
```

| Field | Meaning |
| --- | --- |
| `index_cell_km` | Sparse candidate-grid cell size; it does not reduce coordinate precision. |
| `nearby_location_radius_km` | Maximum straight-line distance for discovered location output. |
| `nearby_path_radius_km` | Maximum perpendicular distance for nearby path output. |
| `on_path_tolerance_km` | Distance treated as being on the path centerline. Up to five times this value is described as alongside. |
| `max_nearby_locations` | Nearest discovered location results retained after exact filtering. |
| `max_nearby_paths` | Nearest path results retained after exact filtering. |
| `location_anchor_tolerance_km` | Maximum distance between coordinates and an asserted named-location anchor. |

Larger radii increase the compiled candidate lists and runtime calculations, but not Storyteller context beyond the configured result limits.

## 5. Geography schema

### 5.1 Location points

```yaml
location_points:
  stone_bridge:
    x_km: 41.80
    y_km: 24.40
    z_m: 263
    path_ids: [kings_road, river_vey]
```

`path_ids` records an exact named relationship such as a crossing. It is not used to find arbitrary nearby paths. RC3 no longer requires `area_ids` or `nearby_ids`.

### 5.2 Typed paths

```yaml
paths:
  kings_road:
    name: King's Road
    type: road
    class: major_maintained
    surface: fitted_stone_and_gravel
    directionality: bidirectional
    nav_points:
      - id: kings_road_001
        x_km: 28.00
        y_km: 14.00
        z_m: 140
        cumulative_km: 0.00
        location_id: southwatch_post
        role: checkpoint
```

A path needs at least two points. `cumulative_km` begins at zero and never decreases. Add points at bends, junctions, crossings, confluences, checkpoints and terrain changes.

For `river`, `creek` and `stream`, increasing point order means upstream-to-downstream. For roads and trails, sequence is a reference direction; `directionality` determines permitted travel.

### 5.3 Areas and polygons

Area semantics remain in `world-spatial.yaml`; their polygon or multipolygon geometry remains in `world-geography.yaml`. RC3 tests the authoritative XY coordinate against geometry on every refresh. Low-level polygon `holes` are actual exclusions, while semantic `contains` nesting does not subtract a child from its parent.

## 6. Coordinate-first navigation state

Spatial Navigation State is host-owned.

```yaml
x_km: 34.25
y_km: 18.70
z_m: 195
position_mode: path_following
location_anchor: bramble_gate
active_path: kings_road
current_nav_index: 2
next_nav_index: 3
next_waypoint_nav_index: 4
travel_direction: forward
```

### Required fields

- `x_km`, `y_km`, `z_m`
- `position_mode`, such as `stationary`, `free_roam` or `path_following`

### Optional location relationship

`location_anchor` may name a catalog location when the player is actually there. The refresh script compares the anchor point with the authoritative position:

- within tolerance: loads full current-location detail;
- outside tolerance: reports `out_of_range` and does not pretend the player is still there;
- unknown ID: reports `unknown` while continuing coordinate queries.

Leave `location_anchor` blank while travelling between named places.

### Optional path relationship

`active_path` and nav indexes are useful when movement follows a known path and the host needs segment grade, travel direction or next-waypoint distance. Leave them blank/zero during unrestricted movement. Nearby-path discovery still tells the Storyteller whether the player is on, alongside or near a road or waterway.

### State examples

Free roaming:

```yaml
x_km: 37.10
y_km: 21.35
z_m: 224
position_mode: free_roam
location_anchor: ""
active_path: ""
current_nav_index: 0
next_nav_index: 0
next_waypoint_nav_index: 0
travel_direction: ""
```

Following beside a road without path-locked progress:

```yaml
x_km: 38.40
y_km: 22.05
z_m: 238
position_mode: free_roam
location_anchor: ""
active_path: ""
current_nav_index: 0
next_nav_index: 0
next_waypoint_nav_index: 0
travel_direction: ""
```

The second state needs no special road flag. If it lies within the configured radius, `nearby_paths` reports the King's Road and its perpendicular distance.

## 7. Local-context output

The refresh script writes:

- `position`: XYZ, mode and location-anchor status;
- `current_location`: full detail only for a validated anchor;
- `current_areas`: every polygonal area containing the coordinate;
- `nearby_locations`: nearest discovered places within radius;
- `nearby_paths`: nearest paths with exact centerline distance, relation, side, segment and projected cumulative distance;
- `active_path`: optional progress, grade, flow and waypoint details.

Path proximity relations:

| Relation | Meaning |
| --- | --- |
| `on_path` | Within `on_path_tolerance_km` of the centerline. |
| `alongside` | Within five times that tolerance, but not on the centerline. |
| `nearby` | Within the wider nearby-path radius. |

`left_of_sequence` and `right_of_sequence` use authored point order. For natural waterways, that order is upstream-to-downstream.

## 8. Movement ownership

The package calculates context from coordinates; it does not infer authoritative movement from prose. The destination world must decide when movement has occurred and update Spatial Navigation State before refresh.

Suitable host patterns include:

- deterministic choice effects that write known destination coordinates;
- scripted travel that interpolates along a path;
- a bounded request/commit mechanism where the AI proposes a destination or delta and mechanical logic validates it before writing coordinates.

Do not let multiple independent systems update coordinates without an explicit owner and ordering rule.

## 9. Runtime components

| Component | Variable | Visibility | Owner |
| --- | --- | --- | --- |
| Spatial Geography Catalog | `$spatial_geography` | hidden | compiler |
| Spatial Location Catalog | `$spatial_locations` | hidden | compiler |
| Spatial Area Catalog | `$spatial_areas` | hidden | compiler |
| Spatial Location State | `$spatial_location_state` | hidden | host world |
| Spatial Navigation State | `$spatial_navigation` | hidden | host world |
| Spatial Local Context | `$spatial_context` | ai_only | refresh script |

## 10. Beginner integration

1. Customize `world-geography.yaml` and `world-spatial.yaml`.
2. Set `initial_navigation` with authoritative XYZ coordinates.
3. Run `python tools/build_spatial_context.py`.
4. Merge all compiled bank components into a complete IW world export.
5. Preserve the six tracker variable names or rewrite every PawScript reference.
6. Ensure host movement commits coordinates before `Refresh Spatial Context` when same-pass context is required.
7. Validate the complete world.
8. Test a named location, off-road coordinate, road-adjacent coordinate, area boundary, polygon hole, active road segment and active river segment in Sandbox and live play.

Raw IW JSON import replaces the complete base-world definition. Export a backup first, and start a new playthrough after editing because existing live copies do not inherit base-world changes.

## 11. Validation and boundaries

The compiler checks source metadata, coordinates, query settings, references, path order, water elevation direction, polygon structure, containment cycles and initial anchor consistency. It generates the sparse grid and rejects indexes above 50,000 cells.

Static checks cannot execute PawScript or certify trigger ordering and model behavior. RC3 remains a release candidate.

Current boundaries:

- XYZ elevation is supplied by the host; no digital elevation model is interpolated.
- Path proximity does not perform route finding.
- Area lookup uses authored 2D polygons; elevation does not affect membership.
- The index accelerates locations and paths. Area records are bounding-box filtered before exact polygon tests.
- Movement inference and travel speed remain world-specific.

## 12. Version policy

| Version | Meaning |
| --- | --- |
| `1.0.RC1` / schema 1.0 | Initial point- and route-based candidate |
| `1.0.RC2` / schema 1.1 | Combined semantic source and typed paths |
| `1.0.RC3` / schema 1.2 | Coordinate-first free roaming and spatial queries |
| `1.0` | First stable release |

Do not mix schemas. See `CHANGELOG.md` for migration steps.

---

END OF DOCUMENT: IW-Spatial-Context.md
