"""Rough census of circular cutouts in remaining MobiFlight face SVGs."""
from __future__ import annotations

import collections
import os
import re

BASE = os.path.join(
    os.path.dirname(__file__),
    "..",
    "vendor",
    "mobiflight-panels",
    "aircraft",
    "airbus-a32x",
)

FILES = [
    ("adirs", r"overhead\adirs\a320-overhead-adirs.svg"),
    ("aircond", r"overhead\aircond\a320-overhead-aircond.svg"),
    ("audio", r"overhead\audio\a320-overhead-audio.svg"),
    ("cargo-heat", r"overhead\cargo-heat\a320-overhead-cargo-heat.svg"),
    ("elec", r"overhead\elec\a320-overhead-elec.svg"),
    ("emer-elec", r"overhead\Emer Elec\a320-overhead-emer-elec.svg"),
    ("evac", r"overhead\evac\a320-overhead-evac.svg"),
    ("fire", r"overhead\fire\a320-overhead-fire.svg"),
    ("flt-ctl", r"overhead\flt-ctl\a320-overhead-flt-ctl.svg"),
    ("flt-ctl-fo", r"overhead\flt-ctl-fo\a320-overhead-flt-ctl-fo.svg"),
    ("gndservices", r"overhead\gndservices\a320-overhead-groundservices.svg"),
    ("hyd-fuel", r"overhead\hyd-fuel\a320-overhead-hydfuel.svg"),
    ("radio", r"overhead\radio\a320-overhead-radio.svg"),
    ("gear", r"main-instrument-panel\gear_lever\A32x_Gear_Lever_Lasercut.svg"),
    ("brake-pressure", r"main-instrument-panel\brake-pressure\a320-brake-pressure.svg"),
    ("terr-on-nd", r"main-instrument-panel\terr-on-nd\A320-terr-on-nd.svg"),
    ("flood", r"pedestal\flood-light\Flood light panel.svg"),
    ("parking-brake", None),  # STL/mech only
]


def main() -> None:
    for name, rel in FILES:
        if rel is None:
            print(f"{name:14} (no face SVG — mechanical handle + transducer)")
            continue
        path = os.path.normpath(os.path.join(BASE, rel))
        text = open(path, encoding="utf-8", errors="ignore").read()
        rs = [float(m) for m in re.findall(r"""\br=["']?([0-9.]+)""", text)]
        rxs = [float(m) for m in re.findall(r"""\brx=["']?([0-9.]+)""", text)]
        vb = re.search(r"""viewBox=["']([^"']+)""", text)
        buckets = collections.Counter(round(r, 1) for r in rs)
        top = buckets.most_common(5)
        print(
            f"{name:14} circles={len(rs):4} ellipses={len(rxs):3} "
            f"top_r={top} vb={vb.group(1) if vb else '?'}"
        )


if __name__ == "__main__":
    main()
