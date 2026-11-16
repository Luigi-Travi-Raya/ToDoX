from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image


PROJECT_DIRECTORY = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = PROJECT_DIRECTORY / "assets" / "branding" / "todox-icon.png"


def load_source(source_path: Path) -> Image.Image:
    with Image.open(source_path) as source:
        source = source.convert("RGBA")
        if source.width != source.height:
            raise ValueError(f"O icone da marca deve ser quadrado: {source_path}")
        return source.copy()


def create_square(source: Image.Image, path: Path, size: int) -> None:
    image = source.resize((size, size), Image.Resampling.LANCZOS)
    image.save(path, optimize=True)


def create_wide(source: Image.Image, path: Path) -> None:
    image = Image.new("RGBA", (310, 150), (0, 0, 0, 0))
    mark = source.resize((134, 134), Image.Resampling.LANCZOS)
    image.alpha_composite(mark, ((image.width - mark.width) // 2, 8))
    image.save(path, optimize=True)


def generate_assets(output: Path, source_path: Path = DEFAULT_SOURCE) -> None:
    output.mkdir(parents=True, exist_ok=True)
    source = load_source(source_path)
    create_square(source, output / "StoreLogo.png", 50)
    create_square(source, output / "Square44x44Logo.png", 44)
    create_square(source, output / "Square150x150Logo.png", 150)
    create_square(source, output / "Square310x310Logo.png", 310)
    create_wide(source, output / "Wide310x150Logo.png")


def main() -> None:
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("msix/Assets")
    source = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_SOURCE
    generate_assets(output.resolve(), source.resolve())


if __name__ == "__main__":
    main()
