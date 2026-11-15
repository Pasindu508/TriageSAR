#!/usr/bin/env python
"""Print the tree of a NISAR HDF5 product and the canonical layers TriageSAR recognises.

    python scripts/inspect_hdf5.py path/to/product.h5
    python scripts/inspect_hdf5.py https://nisar.asf.earthdatacloud.nasa.gov/...h5   # needs Earthdata credentials
"""

from __future__ import annotations

import argparse

from _common import REPO_ROOT, fail
from triagesar.fixture import open_gunw
from triagesar.nisar import hdf5_reader
from triagesar.nisar.authentication import AuthenticationError, bearer_token, resolve_credentials
from triagesar.nisar.metadata import read_metadata
from triagesar.nisar.schema import SchemaError


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="local .h5 path or https URL")
    ap.add_argument("--no-tree", action="store_true", help="only print the recognised canonical layers")
    args = ap.parse_args()
    token = None
    if args.source.startswith("https://"):
        try:
            token = bearer_token(resolve_credentials(REPO_ROOT / ".env"))
        except AuthenticationError as exc:
            fail(str(exc), code=2)
    try:
        h5 = open_gunw(args.source, token)
    except (OSError, ValueError) as exc:
        fail(f"Could not open {args.source}: {exc}")
    with h5:
        if not args.no_tree:
            print("\n".join(hdf5_reader.describe_tree(h5)))
            print()
        try:
            layers = hdf5_reader.discover_layers(h5)
        except SchemaError as exc:
            fail(f"Not a usable GUNW product: {exc}")
        meta = read_metadata(h5)
    print("Recognised canonical layers")
    print(f"  layer group : {layers.layer_group}  (frequency {layers.frequency}, polarisation {layers.polarisation})")
    for name, ref in layers.layers.items():
        print(f"  {name:36s} {ref.hdf5_path}  shape={ref.shape} dtype={ref.dtype} units={ref.units} fill={ref.fill_value}")
    g = layers.grid
    print(f"  grid        : {g.width} x {g.height}, EPSG {g.epsg}, x={g.x_path}, y={g.y_path}")
    w = layers.wavelength
    print(f"  wavelength  : {w.wavelength_m:.6f} m from {w.source_path} ({w.derivation})")
    print(f"  correction layers shipped (never applied silently): {len(layers.available_correction_layers)}")
    for path in layers.available_correction_layers:
        print(f"    {path}")
    print("Identification")
    for key, value in sorted(meta.fields.items()):
        text = str(value)
        print(f"  {key:32s} {text if len(text) < 100 else text[:97] + '...'}")


if __name__ == "__main__":
    main()
