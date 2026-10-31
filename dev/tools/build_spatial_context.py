#!/usr/bin/env python3
"""Validate IW Spatial Context YAML and compile the reusable data-bank bundle."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError as exc:  # pragma: no cover - user environment path
    raise SystemExit("PyYAML is required: python -m pip install PyYAML") from exc


PACKAGE_VERSION = "1.0.RC3"
SCHEMA_VERSION = "1.2"
FLOWING_WATER_TYPES = {"river", "creek", "stream"}


class UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys."""


def _construct_mapping(loader: UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False) -> dict:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping,
)


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def read_yaml(path: Path) -> tuple[str, dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    data = yaml.load(text, Loader=UniqueKeyLoader)
    if not isinstance(data, dict):
        raise ValueError(f"{path.name}: root must be a mapping")
    return text.rstrip("\n"), data


def point_in_ring(point: list[float], ring: list[list[float]]) -> bool:
    x, y = point
    inside = False
    j = len(ring) - 1
    for i, vertex in enumerate(ring):
        xi, yi = vertex
        xj, yj = ring[j]
        crosses = (yi > y) != (yj > y)
        if crosses:
            intersection_x = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < intersection_x:
                inside = not inside
        j = i
    return inside


class Validator:
    def __init__(self, geography: dict, spatial: dict) -> None:
        self.geography = geography
        self.spatial = spatial
        self.locations = spatial
        self.areas = spatial
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def validate_metadata(self, data: dict, role: str, filename: str) -> None:
        metadata = data.get("spatial_context")
        if not isinstance(metadata, dict):
            self.error(f"{filename}: missing spatial_context metadata")
            return
        if str(metadata.get("schema_version")) != SCHEMA_VERSION:
            self.error(
                f"{filename}: schema_version must be {SCHEMA_VERSION!r}; "
                f"found {metadata.get('schema_version')!r}"
            )
        if str(metadata.get("package_version")) != PACKAGE_VERSION:
            self.warn(
                f"{filename}: package_version differs from compiler {PACKAGE_VERSION}; "
                f"found {metadata.get('package_version')!r}"
            )
        if metadata.get("data_role") != role:
            self.error(f"{filename}: data_role must be {role!r}")

    def validate_coordinate_system(self) -> None:
        coordinate_system = self.geography.get("coordinate_system")
        if not isinstance(coordinate_system, dict):
            self.error("world-geography.yaml: coordinate_system must be a mapping")
            return
        expected = {
            "x_unit": "kilometer",
            "y_unit": "kilometer",
            "z_unit": "meter",
            "x_direction": "east",
            "y_direction": "north",
        }
        for key, value in expected.items():
            if coordinate_system.get(key) != value:
                self.error(f"coordinate_system.{key} must be {value!r}")

    def validate_query_settings(self) -> None:
        settings = self.geography.get("query_settings")
        if not isinstance(settings, dict):
            self.error("world-geography.yaml: query_settings must be a mapping")
            return
        for field in (
            "index_cell_km",
            "nearby_location_radius_km",
            "nearby_path_radius_km",
            "on_path_tolerance_km",
            "location_anchor_tolerance_km",
        ):
            value = settings.get(field)
            if not is_number(value) or float(value) <= 0:
                self.error(f"query_settings.{field}: must be a positive number")
        for field in ("max_nearby_locations", "max_nearby_paths"):
            value = settings.get(field)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                self.error(f"query_settings.{field}: must be a positive integer")
        path_radius = settings.get("nearby_path_radius_km")
        tolerance = settings.get("on_path_tolerance_km")
        if is_number(path_radius) and is_number(tolerance) and tolerance > path_radius:
            self.error(
                "query_settings.on_path_tolerance_km must not exceed "
                "nearby_path_radius_km"
            )

    def validate_polygon(self, geometry_id: str, geometry: Any) -> None:
        if not isinstance(geometry, dict) or geometry.get("type") != "polygon":
            self.error(f"polygons.{geometry_id}: must be a polygon mapping")
            return
        outer = geometry.get("outer")
        if not isinstance(outer, list) or len(outer) < 3:
            self.error(f"polygons.{geometry_id}.outer: requires at least three vertices")
            return
        for index, vertex in enumerate(outer, 1):
            if (
                not isinstance(vertex, list)
                or len(vertex) != 2
                or not all(is_number(value) for value in vertex)
            ):
                self.error(
                    f"polygons.{geometry_id}.outer[{index}]: expected [x_km, y_km] numbers"
                )
        holes = geometry.get("holes", [])
        if not isinstance(holes, list):
            self.error(f"polygons.{geometry_id}.holes: must be a list of rings")
        else:
            for hole_index, ring in enumerate(holes, 1):
                if not isinstance(ring, list) or len(ring) < 3:
                    self.error(
                        f"polygons.{geometry_id}.holes[{hole_index}]: requires at least three vertices"
                    )

    def validate_geography(self) -> None:
        points = self.geography.get("location_points")
        paths = self.geography.get("paths")
        polygons = self.geography.get("polygons")
        multipolygons = self.geography.get("multipolygons", {})
        if not isinstance(points, dict):
            self.error("world-geography.yaml: location_points must be a mapping")
            points = {}
        if not isinstance(paths, dict):
            self.error("world-geography.yaml: paths must be a mapping")
            paths = {}
        if not isinstance(polygons, dict):
            self.error("world-geography.yaml: polygons must be a mapping")
            polygons = {}
        if not isinstance(multipolygons, dict):
            self.error("world-geography.yaml: multipolygons must be a mapping")
            multipolygons = {}

        location_catalog = self.locations.get("locations", {})

        for location_id, point in points.items():
            path = f"location_points.{location_id}"
            if not isinstance(point, dict):
                self.error(f"{path}: must be a mapping")
                continue
            for field in ("x_km", "y_km", "z_m"):
                if not is_number(point.get(field)):
                    self.error(f"{path}.{field}: must be a finite number")
            if location_id not in location_catalog:
                self.error(f"{path}: has no matching world-spatial locations entry")
            for path_id in point.get("path_ids", []):
                if path_id not in paths:
                    self.error(f"{path}.path_ids: unknown path {path_id!r}")
            if "area_ids" in point:
                self.warn(f"{path}.area_ids is deprecated in schema 1.2 and ignored")
            if "nearby_ids" in point:
                self.warn(f"{path}.nearby_ids is deprecated in schema 1.2 and ignored")

        for location_id in location_catalog:
            if location_id not in points:
                self.warn(f"locations.{location_id}: has no matching geography point")

        for path_id, path_record in paths.items():
            path = f"paths.{path_id}"
            if not isinstance(path_record, dict):
                self.error(f"{path}: must be a mapping")
                continue
            path_type = path_record.get("type")
            if not isinstance(path_type, str) or not path_type.strip():
                self.error(f"{path}.type: required nonempty string")
                path_type = ""
            nav_points = path_record.get("nav_points")
            if not isinstance(nav_points, list) or len(nav_points) < 2:
                self.error(f"{path}.nav_points: requires at least two points")
                continue
            previous_cumulative: float | None = None
            previous_point: dict | None = None
            calculated_cumulative = 0.0
            seen_nav_ids: set[str] = set()
            for index, nav in enumerate(nav_points, 1):
                nav_path = f"{path}.nav_points[{index}]"
                if not isinstance(nav, dict):
                    self.error(f"{nav_path}: must be a mapping")
                    continue
                nav_id = nav.get("id")
                if not isinstance(nav_id, str) or not nav_id:
                    self.error(f"{nav_path}.id: required nonempty string")
                elif nav_id in seen_nav_ids:
                    self.error(f"{nav_path}.id: duplicate nav-point ID {nav_id!r}")
                else:
                    seen_nav_ids.add(nav_id)
                for field in ("x_km", "y_km", "z_m", "cumulative_km"):
                    if not is_number(nav.get(field)):
                        self.error(f"{nav_path}.{field}: must be a finite number")
                cumulative = nav.get("cumulative_km")
                if is_number(cumulative):
                    if index == 1 and abs(float(cumulative)) > 0.001:
                        self.error(f"{nav_path}.cumulative_km: first point must be zero")
                    if previous_cumulative is not None and cumulative < previous_cumulative:
                        self.error(f"{nav_path}.cumulative_km: must not decrease")
                    previous_cumulative = float(cumulative)
                location_id = nav.get("location_id")
                if location_id is not None and location_id not in location_catalog:
                    self.error(f"{nav_path}.location_id: unknown location {location_id!r}")
                if "area_ids" in nav:
                    self.warn(f"{nav_path}.area_ids is deprecated in schema 1.2 and ignored")
                if previous_point is not None and all(
                    is_number(nav.get(k)) and is_number(previous_point.get(k))
                    for k in ("x_km", "y_km")
                ):
                    calculated_cumulative += math.hypot(
                        nav["x_km"] - previous_point["x_km"],
                        nav["y_km"] - previous_point["y_km"],
                    )
                    if is_number(cumulative) and abs(cumulative - calculated_cumulative) > 0.25:
                        self.warn(
                            f"{nav_path}.cumulative_km differs from XY polyline length by "
                            f"{abs(cumulative - calculated_cumulative):.2f} km"
                        )
                if (
                    path_type in FLOWING_WATER_TYPES
                    and previous_point is not None
                    and is_number(previous_point.get("z_m"))
                    and is_number(nav.get("z_m"))
                    and float(nav["z_m"]) > float(previous_point["z_m"]) + 0.5
                ):
                    self.warn(
                        f"{nav_path}.z_m rises along a {path_type}; flowing-water "
                        "nav points should normally run upstream to downstream"
                    )
                previous_point = nav

        for geometry_id, geometry in polygons.items():
            self.validate_polygon(geometry_id, geometry)

        for geometry_id, geometry in multipolygons.items():
            path = f"multipolygons.{geometry_id}"
            if not isinstance(geometry, dict) or geometry.get("type") != "multipolygon":
                self.error(f"{path}: must be a multipolygon mapping")
                continue
            members = geometry.get("members")
            if not isinstance(members, list) or not members:
                self.error(f"{path}.members: requires at least one polygon ID")
                continue
            for member in members:
                if member not in polygons:
                    self.error(f"{path}.members: unknown polygon {member!r}")

    def validate_locations(self) -> None:
        locations = self.locations.get("locations")
        if not isinstance(locations, dict):
            self.error("world-spatial.yaml: locations must be a mapping")
            return
        for location_id, location in locations.items():
            path = f"locations.{location_id}"
            if not isinstance(location, dict):
                self.error(f"{path}: must be a mapping")
                continue
            for field in ("name", "kind", "summary"):
                if not isinstance(location.get(field), str) or not location[field].strip():
                    self.error(f"{path}.{field}: required nonempty string")
            initial_state = location.get("initial_state", {})
            if not isinstance(initial_state, dict):
                self.error(f"{path}.initial_state: must be a mapping")

    def validate_areas(self) -> None:
        areas = self.areas.get("areas")
        if not isinstance(areas, dict):
            self.error("world-spatial.yaml: areas must be a mapping")
            return
        polygons = self.geography.get("polygons", {})
        multipolygons = self.geography.get("multipolygons", {})
        for area_id, area in areas.items():
            path = f"areas.{area_id}"
            if not isinstance(area, dict):
                self.error(f"{path}: must be a mapping")
                continue
            for field in ("name", "layer", "kind", "geometry", "summary"):
                if not isinstance(area.get(field), str) or not area[field].strip():
                    self.error(f"{path}.{field}: required nonempty string")
            if "holes" in area:
                self.error(f"{path}.holes: semantic areas use contains; holes belong to polygon geometry")
            geometry_id = area.get("geometry")
            if geometry_id not in polygons and geometry_id not in multipolygons:
                self.error(f"{path}.geometry: unknown geometry {geometry_id!r}")
            contains = area.get("contains")
            if not isinstance(contains, list):
                self.error(f"{path}.contains: required list")
                continue
            for child in contains:
                if child not in areas:
                    self.error(f"{path}.contains: unknown child area {child!r}")
                if child == area_id:
                    self.error(f"{path}.contains: an area cannot contain itself")

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(area_id: str, trail: list[str]) -> None:
            if area_id in visiting:
                cycle = " -> ".join(trail + [area_id])
                self.error(f"area containment cycle: {cycle}")
                return
            if area_id in visited or area_id not in areas:
                return
            visiting.add(area_id)
            for child in areas[area_id].get("contains", []):
                visit(child, trail + [area_id])
            visiting.remove(area_id)
            visited.add(area_id)

        for area_id in areas:
            visit(area_id, [])

        for parent_id, parent in areas.items():
            parent_geometry = polygons.get(parent.get("geometry"))
            if not isinstance(parent_geometry, dict):
                continue
            parent_ring = parent_geometry.get("outer")
            if not isinstance(parent_ring, list) or len(parent_ring) < 3:
                continue
            for child_id in parent.get("contains", []):
                child = areas.get(child_id, {})
                child_geometry = polygons.get(child.get("geometry"))
                if not isinstance(child_geometry, dict):
                    continue
                child_ring = child_geometry.get("outer")
                if not isinstance(child_ring, list):
                    continue
                outside = [vertex for vertex in child_ring if not point_in_ring(vertex, parent_ring)]
                if outside:
                    self.warn(
                        f"areas.{parent_id}.contains {child_id!r}, but "
                        f"{len(outside)} child polygon vertex/vertices appear outside the parent"
                    )

    def validate_initial_navigation(self) -> None:
        nav = self.geography.get("initial_navigation", {})
        if not isinstance(nav, dict):
            self.error("initial_navigation must be a mapping")
            return
        points = self.geography.get("location_points", {})
        paths = self.geography.get("paths", {})
        for field in ("x_km", "y_km", "z_m"):
            if not is_number(nav.get(field)):
                self.error(f"initial_navigation.{field}: must be a finite number")
        position_mode = nav.get("position_mode")
        if not isinstance(position_mode, str) or not position_mode.strip():
            self.error("initial_navigation.position_mode: required nonempty string")
        location_anchor = nav.get("location_anchor", "")
        if location_anchor and location_anchor not in points:
            self.error(f"initial_navigation.location_anchor: unknown location {location_anchor!r}")
        if location_anchor in points and all(is_number(nav.get(k)) for k in ("x_km", "y_km")):
            anchor = points[location_anchor]
            distance = math.hypot(nav["x_km"] - anchor["x_km"], nav["y_km"] - anchor["y_km"])
            tolerance = self.geography.get("query_settings", {}).get(
                "location_anchor_tolerance_km", 0
            )
            if is_number(tolerance) and distance > tolerance:
                self.error(
                    f"initial_navigation.location_anchor is {distance:.2f} km from the "
                    f"authoritative coordinates; tolerance is {tolerance:.2f} km"
                )
        path_id = nav.get("active_path", "")
        if path_id and path_id not in paths:
            self.error(f"initial_navigation.active_path: unknown path {path_id!r}")
            return
        if path_id:
            count = len(paths[path_id].get("nav_points", []))
            for field in ("current_nav_index", "next_nav_index", "next_waypoint_nav_index"):
                value = nav.get(field, 0)
                if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                    self.error(f"initial_navigation.{field}: must be a nonnegative integer")
                elif value > count:
                    self.error(
                        f"initial_navigation.{field}: {value} exceeds path nav-point count {count}"
                    )
            current_index = nav.get("current_nav_index", 0)
            next_index = nav.get("next_nav_index", 0)
            direction = nav.get("travel_direction", "")
            if (
                isinstance(current_index, int)
                and isinstance(next_index, int)
                and current_index > 0
                and next_index > 0
            ):
                if direction == "forward" and next_index <= current_index:
                    self.error(
                        "initial_navigation.travel_direction is forward, but next_nav_index "
                        "does not advance along the path sequence"
                    )
                if direction == "reverse" and next_index >= current_index:
                    self.error(
                        "initial_navigation.travel_direction is reverse, but next_nav_index "
                        "does not move backward along the path sequence"
                    )

    def run(self) -> None:
        self.validate_metadata(self.geography, "geography", "world-geography.yaml")
        self.validate_metadata(self.spatial, "spatial", "world-spatial.yaml")
        self.validate_coordinate_system()
        self.validate_query_settings()
        self.validate_locations()
        self.validate_areas()
        self.validate_geography()
        self.validate_initial_navigation()


def find_tracker_components(bank: dict) -> dict[str, dict]:
    trackers: dict[str, dict] = {}
    for entry in bank.get("entries", []):
        for component in entry.get("components", []):
            if component.get("kind") != "trackedItem":
                continue
            payload = component.get("payload", {})
            variable_name = payload.get("variableName")
            if isinstance(variable_name, str):
                trackers[variable_name] = payload
    return trackers


def yaml_text(value: Any) -> str:
    return yaml.safe_dump(
        value,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    ).rstrip("\n")


def _ring_bounds(ring: list[list[float]]) -> dict[str, float]:
    xs = [float(vertex[0]) for vertex in ring]
    ys = [float(vertex[1]) for vertex in ring]
    return {
        "min_x_km": min(xs),
        "max_x_km": max(xs),
        "min_y_km": min(ys),
        "max_y_km": max(ys),
    }


def build_spatial_index(geography: dict[str, Any]) -> dict[str, Any]:
    """Build sparse location/path candidates and geometry bounds for runtime queries."""
    settings = geography["query_settings"]
    cell_size = float(settings["index_cell_km"])
    location_radius = float(settings["nearby_location_radius_km"])
    path_radius = float(settings["nearby_path_radius_km"])
    cells: dict[tuple[int, int], dict[str, set[str]]] = {}

    def add_bbox(
        candidate_kind: str,
        candidate_id: str,
        min_x: float,
        max_x: float,
        min_y: float,
        max_y: float,
    ) -> None:
        min_cell_x = math.floor(min_x / cell_size)
        max_cell_x = math.floor(max_x / cell_size)
        min_cell_y = math.floor(min_y / cell_size)
        max_cell_y = math.floor(max_y / cell_size)
        for cell_x in range(min_cell_x, max_cell_x + 1):
            for cell_y in range(min_cell_y, max_cell_y + 1):
                cell = cells.setdefault(
                    (cell_x, cell_y), {"location_ids": set(), "path_ids": set()}
                )
                cell[candidate_kind].add(candidate_id)

    for location_id, point in geography.get("location_points", {}).items():
        x = float(point["x_km"])
        y = float(point["y_km"])
        add_bbox(
            "location_ids",
            location_id,
            x - location_radius,
            x + location_radius,
            y - location_radius,
            y + location_radius,
        )

    for path_id, path_record in geography.get("paths", {}).items():
        nav_points = path_record.get("nav_points", [])
        for index in range(len(nav_points) - 1):
            start = nav_points[index]
            end = nav_points[index + 1]
            add_bbox(
                "path_ids",
                path_id,
                min(float(start["x_km"]), float(end["x_km"])) - path_radius,
                max(float(start["x_km"]), float(end["x_km"])) + path_radius,
                min(float(start["y_km"]), float(end["y_km"])) - path_radius,
                max(float(start["y_km"]), float(end["y_km"])) + path_radius,
            )

    polygons = geography.get("polygons", {})
    geometry_bounds: dict[str, dict[str, float]] = {}
    for geometry_id, polygon in polygons.items():
        geometry_bounds[geometry_id] = _ring_bounds(polygon["outer"])
    for geometry_id, multipolygon in geography.get("multipolygons", {}).items():
        member_bounds = [geometry_bounds[member] for member in multipolygon.get("members", [])]
        if member_bounds:
            geometry_bounds[geometry_id] = {
                "min_x_km": min(item["min_x_km"] for item in member_bounds),
                "max_x_km": max(item["max_x_km"] for item in member_bounds),
                "min_y_km": min(item["min_y_km"] for item in member_bounds),
                "max_y_km": max(item["max_y_km"] for item in member_bounds),
            }

    if len(cells) > 50000:
        raise ValueError(
            f"compiled spatial index would contain {len(cells)} cells; increase "
            "query_settings.index_cell_km or reduce query radii"
        )

    serialized_cells: dict[str, dict[str, list[str]]] = {}
    for (cell_x, cell_y), values in sorted(cells.items()):
        serialized_cells[f"{cell_x}_{cell_y}"] = {
            "location_ids": sorted(values["location_ids"]),
            "path_ids": sorted(values["path_ids"]),
        }
    return {
        "cell_size_km": cell_size,
        "cells": serialized_cells,
        "geometry_bounds": geometry_bounds,
    }


def add_runtime_segments(geography: dict[str, Any]) -> None:
    """Add edge and segment lists that avoid index arithmetic in PawScript loops."""

    def ring_edges(ring: list[list[float]]) -> list[dict[str, float]]:
        edges: list[dict[str, float]] = []
        previous = ring[-1]
        for vertex in ring:
            edges.append(
                {
                    "x1_km": float(vertex[0]),
                    "y1_km": float(vertex[1]),
                    "x2_km": float(previous[0]),
                    "y2_km": float(previous[1]),
                }
            )
            previous = vertex
        return edges

    for polygon in geography.get("polygons", {}).values():
        polygon["runtime_outer_edges"] = ring_edges(polygon["outer"])
        polygon["runtime_holes"] = [
            {"edges": ring_edges(hole)} for hole in polygon.get("holes", [])
        ]

    for path_record in geography.get("paths", {}).values():
        nav_points = path_record.get("nav_points", [])
        segments: list[dict[str, Any]] = []
        for index in range(len(nav_points) - 1):
            start = nav_points[index]
            end = nav_points[index + 1]
            segments.append(
                {
                    "index": index + 1,
                    "start_x_km": start["x_km"],
                    "start_y_km": start["y_km"],
                    "start_z_m": start["z_m"],
                    "start_cumulative_km": start["cumulative_km"],
                    "end_x_km": end["x_km"],
                    "end_y_km": end["y_km"],
                    "end_z_m": end["z_m"],
                    "end_cumulative_km": end["cumulative_km"],
                }
            )
        path_record["runtime_segments"] = segments


def compile_bundle(
    template: dict,
    source_texts: dict[str, str],
    pawscript_text: str,
    geography: dict,
    spatial: dict,
    output_path: Path,
) -> None:
    bank = copy.deepcopy(template)
    trackers = find_tracker_components(bank)
    required = {
        "spatial_geography",
        "spatial_locations",
        "spatial_areas",
        "spatial_location_state",
        "spatial_navigation",
        "spatial_context",
    }
    missing = required.difference(trackers)
    if missing:
        raise ValueError(f"bundle template is missing tracker variables: {sorted(missing)}")

    location_state = {
        "locations": {
            location_id: copy.deepcopy(location.get("initial_state", {}))
            for location_id, location in spatial.get("locations", {}).items()
        }
    }
    navigation_state = copy.deepcopy(geography.get("initial_navigation", {}))

    compiled_geography = copy.deepcopy(geography)
    compiled_geography["spatial_index"] = build_spatial_index(geography)
    add_runtime_segments(compiled_geography)
    trackers["spatial_geography"]["initialValue"] = yaml_text(compiled_geography)
    trackers["spatial_locations"]["initialValue"] = yaml_text(
        {"locations": copy.deepcopy(spatial.get("locations", {}))}
    )
    trackers["spatial_areas"]["initialValue"] = yaml_text(
        {"areas": copy.deepcopy(spatial.get("areas", {}))}
    )
    trackers["spatial_location_state"]["initialValue"] = yaml_text(location_state)
    trackers["spatial_navigation"]["initialValue"] = yaml_text(navigation_state)

    bank["package"]["compiled"] = True
    bank["package"]["sourceDigests"] = {
        key: hashlib.sha256(text.encode("utf-8")).hexdigest()
        for key, text in {**source_texts, "pawscript": pawscript_text}.items()
    }
    script_effects = [
        effect
        for entry in bank.get("entries", [])
        for component in entry.get("components", [])
        if component.get("kind") == "triggerEvent"
        for effect in component.get("payload", {}).get("triggerEffects", [])
        if effect.get("type") == "effectRunScript"
        and effect.get("name") == "Assemble Local Spatial Context"
    ]
    if len(script_effects) != 1:
        raise ValueError(
            "bundle template must contain exactly one Assemble Local Spatial Context script effect"
        )
    script_effects[0]["data"] = pawscript_text
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(bank, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    package_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--geography", type=Path, default=package_root / "world-geography.yaml")
    parser.add_argument("--spatial", type=Path, default=package_root / "world-spatial.yaml")
    parser.add_argument(
        "--template",
        type=Path,
        default=package_root / "IW-Spatial-Context-Bundle.template.json",
    )
    parser.add_argument(
        "--pawscript",
        type=Path,
        default=package_root / "src" / "Refresh-Spatial-Context.pawscript",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=package_root / "IW-Spatial-Context-Bundle.json",
    )
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        geography_text, geography = read_yaml(args.geography)
        spatial_text, spatial = read_yaml(args.spatial)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    validator = Validator(geography, spatial)
    validator.run()
    for warning in validator.warnings:
        print(f"WARNING: {warning}")
    for error in validator.errors:
        print(f"ERROR: {error}", file=sys.stderr)
    if validator.errors:
        print(
            f"Validation failed: {len(validator.errors)} error(s), "
            f"{len(validator.warnings)} warning(s).",
            file=sys.stderr,
        )
        return 1

    if args.validate_only:
        print(f"Validation passed with {len(validator.warnings)} warning(s).")
        return 0

    try:
        template = json.loads(args.template.read_text(encoding="utf-8"))
        pawscript_text = args.pawscript.read_text(encoding="utf-8").rstrip("\n")
        compile_bundle(
            template,
            {
                "geography": geography_text,
                "spatial": spatial_text,
            },
            pawscript_text,
            geography,
            spatial,
            args.out,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(
        f"Compiled {args.out} with {len(validator.warnings)} warning(s). "
        "IW/PawScript runtime validation has not been performed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
