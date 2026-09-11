"""Restore upstream map notices beside the locally generated offline database."""
import argparse
from pathlib import Path
from urllib.request import urlopen

SOURCES = {
    "OpenFreeMap-LICENSE.md": "https://raw.githubusercontent.com/hyperknot/openfreemap/main/LICENSE.md",
    "OSM-Liberty-LICENSE.md": "https://raw.githubusercontent.com/maputnik/osm-liberty/gh-pages/LICENSE.md",
    "OpenMapTiles-LICENSE.md": "https://raw.githubusercontent.com/openmaptiles/openmaptiles/master/LICENSE.md",
    "Noto-Sans-OFL.txt": "https://raw.githubusercontent.com/google/fonts/main/ofl/notosans/OFL.txt",
    "Maki-LICENSE.txt": "https://raw.githubusercontent.com/mapbox/maki/master/LICENSE.txt",
}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("map_directory", type=Path)
    target = parser.parse_args().map_directory
    notices = target / "licenses"
    notices.mkdir(parents=True, exist_ok=True)
    for name, url in SOURCES.items():
        with urlopen(url, timeout=30) as response:
            data = response.read()
        if len(data) < 100:
            raise ValueError(f"Invalid notice: {name}")
        (notices / name).write_bytes(data)
    (target / "MAP_LICENSE.txt").write_text(
        "Jinju regional map: OpenFreeMap / OpenMapTiles / OpenStreetMap contributors.\n"
        "OSM data: ODbL https://www.openstreetmap.org/copyright\n"
        "Bounds: 35.03..35.47 latitude, 127.87..128.46 longitude; zoom 7..14.\n"
        "Full upstream notices are in licenses/. Map attribution is retained in the app.\n",
        encoding="utf-8",
    )
    print(f"Restored {len(SOURCES)} notices in {notices}")
