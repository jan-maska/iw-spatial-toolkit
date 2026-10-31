# IW Spatial Context

**Package version:** 1.0.RC3  
**Schema version:** 1.2  
**Status:** Release candidate; IW Sandbox and live-play testing still required

IW Spatial Context is a reusable authoring package for Infinite Worlds projects. It stores the complete map in hidden, script-readable trackers and exposes only a compact local slice to the Storyteller.

## What changed in RC3

- Absolute `x_km`, `y_km`, `z_m` coordinates are now the authoritative player position.
- A named `location_anchor` is optional and accepted only when it agrees with the coordinates.
- `active_path` is optional. Free-roam context remains valid without path indexes.
- The compiler creates a sparse grid index for nearby-location and nearby-path candidates.
- The refresh script dynamically resolves containing polygon areas, discovered nearby locations and path proximity.
- Nearby-path output distinguishes `on_path`, `alongside` and `nearby`, including side of the authored path sequence and projected along-path distance.
- Roads and waterways can therefore be recognized while the player crosses them, follows beside them or approaches them off-path.
- RC2’s author-maintained `area_ids` and `nearby_ids` caches are no longer needed.

## Files

| File | Purpose |
| --- | --- |
| `IW-Spatial-Context.md` | Builder-facing implementation contract |
| `IW-Spatial-Context-Bundle.template.json` | Reusable IW data-bank component template |
| `IW-Spatial-Context-Bundle.json` | Bundle compiled from the included sample YAML |
| `IW-Spatial-Context-Reference.html` | Self-contained reference and beginner guide |
| `world-geography.yaml` | Coordinates, query settings, typed paths and polygon geometry |
| `world-spatial.yaml` | Location descriptions and semantic area definitions |
| `src/Refresh-Spatial-Context.pawscript` | Development source embedded into the JSON bundle |
| `tools/build_spatial_context.py` | Validation, spatial indexing and bundle compiler |
| `manifest.json` | SHA-256 inventory for the release files |
| `CHANGELOG.md` | Package history and migration notes |

## Build

```bash
python tools/build_spatial_context.py
```

This validates both YAML sources, creates the spatial index and writes `IW-Spatial-Context-Bundle.json`. The bundle is a portable data bank, not a partial IW world import. Merge its components into a complete IW world export, preserve the six tracker variable names, and validate the complete world.

## Runtime model

1. Host-world movement logic writes authoritative XYZ coordinates to Spatial Navigation State.
2. Optional `location_anchor` and `active_path` values add named-place detail or path-progress detail; neither is required.
3. The refresh trigger calculates current areas, nearby discovered places and nearby paths from coordinates.
4. Only Spatial Local Context and a short rules block reach the Storyteller.

The package does not infer movement from free text. A destination world must decide when movement becomes authoritative and update the coordinate tracker before refresh.

## Start here

Open `IW-Spatial-Context-Reference.html`. The **Beginner guide** covers world creation and integration; **Free roaming** explains the coordinate-first state contract and provides stationary, off-road and path-following examples.
