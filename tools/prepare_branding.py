"""Prepare supplied brand PNGs for Tk (development only; requires Pillow).

Usage: python tools/prepare_branding.py koenekt-logo.png vector-logo.png
No source files, fonts or personal paths are embedded in the output.
"""
import argparse
from pathlib import Path

from PIL import Image


def prepare(koenekt, vector, destination):
    destination.mkdir(parents=True, exist_ok=True)
    logo = Image.open(koenekt).convert("RGBA")
    logo = logo.crop(logo.getbbox())
    header = logo.copy()
    header.thumbnail((360, 92), Image.Resampling.LANCZOS)
    header.save(destination / "koenekt-header.png", optimize=True)
    logo.thumbnail((1320, 340), Image.Resampling.LANCZOS)
    plate = Image.new("RGBA", (1320, 340))
    plate.alpha_composite(logo, ((1320-logo.width)//2, (340-logo.height)//2))
    paper = Image.new("RGBA", plate.size, "white")
    full = Image.alpha_composite(paper, plate)
    strip = Image.new("RGB", (1320, 340*21), "white")
    for frame in range(21):
        strip.paste(Image.blend(paper, full, frame/20).convert("RGB"), (0, frame*340))
    strip.save(destination / "koenekt-fade.png", optimize=True)
    vector_logo = Image.open(vector).convert("RGBA")
    vector_logo.thumbnail((320, 120), Image.Resampling.LANCZOS)
    vector_logo.save(destination / "vector.png", optimize=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("koenekt", type=Path)
    parser.add_argument("vector", type=Path)
    parser.add_argument("--output", type=Path,
                        default=Path(__file__).resolve().parents[1] / "assets")
    args = parser.parse_args()
    prepare(args.koenekt, args.vector, args.output)
