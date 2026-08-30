"""KML/KMZ contour map parser.

Handles:
- KMZ: unzip the archive, locate the .kml entry inside
- KML: parse with lxml using namespace-agnostic XPath
- Robust to the ``py:pytype`` and similar non-standard attributes
  present in some Google Earth exports.

Output: ContourDataset — a list of (elevation, list of (lon, lat)) polylines.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import numpy as np
from lxml import etree


# ---------------------------------------------------------------------------
# Public data structures
# ---------------------------------------------------------------------------


@dataclass
class ContourPolyline:
    elevation: float
    """Elevation in metres."""

    coords: list[tuple[float, float]]
    """List of (longitude, latitude) pairs in WGS84."""


@dataclass
class ContourDataset:
    polylines: list[ContourPolyline] = field(default_factory=list)
    """All parsed contour polylines, in arbitrary order."""

    # Derived statistics — populated by _compute_stats()
    elevation_min: float = 0.0
    elevation_max: float = 0.0
    contour_interval_m: float = 1.0

    def _compute_stats(self) -> None:
        if not self.polylines:
            return
        elevations = sorted({p.elevation for p in self.polylines})
        self.elevation_min = elevations[0]
        self.elevation_max = elevations[-1]
        if len(elevations) >= 2:
            diffs = np.diff(elevations)
            # Take the most common difference as the contour interval
            vals, counts = np.unique(np.round(diffs, 3), return_counts=True)
            self.contour_interval_m = float(vals[counts.argmax()])
        else:
            self.contour_interval_m = 0.0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _strip_ns(tag: str) -> str:
    """Return the local name without namespace prefix."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _parse_coordinates(text: str) -> list[tuple[float, float]]:
    """Parse a KML ``<coordinates>`` text block into (lon, lat) tuples.

    Each coordinate triplet is ``lon,lat[,alt]``.  Altitude is discarded.
    """
    coords: list[tuple[float, float]] = []
    for token in text.split():
        token = token.strip()
        if not token:
            continue
        parts = token.split(",")
        if len(parts) < 2:
            continue
        try:
            lon = float(parts[0])
            lat = float(parts[1])
        except ValueError:
            continue
        coords.append((lon, lat))
    return coords


def _elevation_from_name(name: str) -> float | None:
    """Extract a numeric elevation from a placemark name string.

    Common formats seen in exported contour KMLs:
      - "274" / "274.0" / "274 m" / "Elevation: 274"
    Falls back to None if nothing numeric is found.
    """
    import re

    # strip non-numeric junk from both ends and look for a float
    m = re.search(r"[-+]?\d+(?:\.\d+)?", name.replace(",", "."))
    if m:
        return float(m.group())
    return None


def _iter_placemarks(root: etree._Element) -> list[etree._Element]:
    """Return all <Placemark> elements regardless of KML namespace."""
    return root.findall(".//{*}Placemark")


def _parse_kml_tree(root: etree._Element) -> ContourDataset:
    """Walk the KML element tree and extract contour polylines."""
    dataset = ContourDataset()

    for pm in _iter_placemarks(root):
        # --- elevation: prefer <altitudeMode> numeric sibling or name ---
        name_el = pm.find("{*}name")
        name_text = (name_el.text or "").strip() if name_el is not None else ""

        # Some exports store elevation in extended data
        elevation: float | None = None

        # 1. Try <name>
        elevation = _elevation_from_name(name_text)

        # 2. Try ExtendedData / SimpleData[@name='elevation'] or similar
        if elevation is None:
            for sd in pm.iter("{*}SimpleData"):
                attr_name = (sd.get("name") or "").lower()
                if "elev" in attr_name or "alt" in attr_name:
                    try:
                        elevation = float(sd.text or "")
                        break
                    except (TypeError, ValueError):
                        pass

        if elevation is None:
            # Skip placemarks we can't assign an elevation to
            continue

        # --- geometry: look for LineString or MultiGeometry > LineString ---
        coords_els = pm.findall(".//{*}coordinates")
        for coords_el in coords_els:
            coords = _parse_coordinates(coords_el.text or "")
            if len(coords) >= 2:
                dataset.polylines.append(
                    ContourPolyline(elevation=elevation, coords=coords)
                )

    dataset._compute_stats()
    return dataset


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_kml_bytes(data: bytes, *, source_name: str = "<bytes>") -> ContourDataset:
    """Parse KML content from a bytes buffer.

    Raises ``ValueError`` on parse failure or empty dataset.
    """
    try:
        root = etree.fromstring(data)
    except etree.XMLSyntaxError as exc:
        raise ValueError(f"XML parse error in {source_name}: {exc}") from exc

    dataset = _parse_kml_tree(root)
    if not dataset.polylines:
        raise ValueError(
            f"No contour polylines could be extracted from {source_name}. "
            "Make sure the file contains Placemarks with numeric names and LineString geometries."
        )
    return dataset


def parse_kml_file(path: str) -> ContourDataset:
    """Parse a KML or KMZ file from disk.

    Raises ``ValueError`` on unsupported format or parse failure.
    """
    p = Path(path)
    ext = p.suffix.lower()

    if ext == ".kmz":
        try:
            with zipfile.ZipFile(path, "r") as zf:
                # The primary KML entry is typically named 'doc.kml' or the
                # first .kml entry found in the archive root.
                kml_names = [n for n in zf.namelist() if n.lower().endswith(".kml")]
                if not kml_names:
                    raise ValueError(f"No .kml file found inside KMZ archive '{p.name}'.")
                # Prefer 'doc.kml' at the root if present
                primary = next(
                    (n for n in kml_names if n.lower() in ("doc.kml", "document.kml")),
                    kml_names[0],
                )
                data = zf.read(primary)
        except zipfile.BadZipFile as exc:
            raise ValueError(f"Cannot open KMZ '{p.name}' as a ZIP archive: {exc}") from exc
        return parse_kml_bytes(data, source_name=primary)

    elif ext == ".kml":
        try:
            data = p.read_bytes()
        except OSError as exc:
            raise ValueError(f"Cannot read file '{p.name}': {exc}") from exc
        return parse_kml_bytes(data, source_name=p.name)

    else:
        raise ValueError(f"Unsupported file extension '{ext}'. Provide a .kml or .kmz file.")
