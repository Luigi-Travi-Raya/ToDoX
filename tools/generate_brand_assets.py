from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


PROJECT_DIRECTORY = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = PROJECT_DIRECTORY / "frontend" / "public" / "todox-logo-v2.png"
DEFAULT_OUTPUT = PROJECT_DIRECTORY / "assets" / "branding"

ICON_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)
MASTER_SIZE = 512
MARK_WIDTH_RATIO = 0.86
MARK_LEFT_PADDING_RATIO = 0.10
X_SCALE = 1.24

BRIGHT_PURPLE_TOP = (154, 82, 255)
BRIGHT_PURPLE_BOTTOM = (115, 44, 229)


def _load_mark(source_path: Path) -> Image.Image:
    with Image.open(source_path) as source:
        source = source.convert("RGBA")
        bounds = source.getchannel("A").getbbox()
        if bounds is None:
            raise ValueError(f"A logo nao possui pixels visiveis: {source_path}")
        return source.crop(bounds)


def _vertical_gradient(
    mask: Image.Image,
    top: tuple[int, int, int],
    bottom: tuple[int, int, int],
) -> Image.Image:
    gradient = Image.new("RGBA", mask.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(gradient)
    denominator = max(1, mask.height - 1)
    for y in range(mask.height):
        progress = y / denominator
        color = tuple(
            round(start * (1 - progress) + end * progress)
            for start, end in zip(top, bottom)
        )
        draw.line((0, y, mask.width, y), fill=(*color, 255))
    gradient.putalpha(mask)
    return gradient


def _extract_bar(mark: Image.Image) -> Image.Image:
    top_region = mark.crop((0, 0, mark.width, round(mark.height * 0.25)))
    bounds = top_region.getchannel("A").getbbox()
    if bounds is None:
        raise ValueError("Nao foi possivel localizar as linhas da logo.")
    return top_region.crop(bounds)


def _extract_x(mark: Image.Image) -> Image.Image:
    raw_mask = Image.new("L", mark.size, 0)
    raw_mask.putdata(
        [
            alpha
            if alpha > 64 and red < 125 and green < 60 and blue < 210
            else 0
            for red, green, blue, alpha in mark.get_flattened_data()
        ]
    )
    core_bounds = raw_mask.getbbox()
    if core_bounds is None:
        raise ValueError("Nao foi possivel separar o X da logo.")

    core_mask = raw_mask.crop(core_bounds)
    core_mask = core_mask.filter(ImageFilter.MaxFilter(7)).filter(
        ImageFilter.GaussianBlur(1.2)
    )
    core_colors = mark.crop(core_bounds)
    core_colors.putalpha(core_mask)

    padding = max(2, round(mark.height * 0.06))
    padded_size = (
        core_mask.width + (padding * 2),
        core_mask.height + (padding * 2),
    )
    padded_core_mask = Image.new("L", padded_size, 0)
    padded_core_mask.paste(core_mask, (padding, padding))

    outline_radius = max(1, round(mark.height * 0.055))
    outline_kernel = (outline_radius * 2) + 1
    outline_mask = padded_core_mask.filter(
        ImageFilter.MaxFilter(outline_kernel)
    ).filter(ImageFilter.GaussianBlur(1.2))
    result = _vertical_gradient(
        outline_mask,
        BRIGHT_PURPLE_TOP,
        BRIGHT_PURPLE_BOTTOM,
    )
    result.alpha_composite(core_colors, (padding, padding))
    return result


def _compose_colored_mark(source_path: Path) -> Image.Image:
    mark = _load_mark(source_path)
    bar = _extract_bar(mark)
    canvas = Image.new(
        "RGBA",
        (round(mark.width * 1.12), round(mark.height * 1.13)),
        (0, 0, 0, 0),
    )
    for y_ratio in (0.0, 0.297, 0.592):
        canvas.alpha_composite(bar, (0, round(mark.height * y_ratio)))

    x_mark = _extract_x(mark)
    x_mark = x_mark.resize(
        (
            round(x_mark.width * X_SCALE),
            round(x_mark.height * X_SCALE),
        ),
        Image.Resampling.LANCZOS,
    )
    canvas.alpha_composite(
        x_mark,
        (round(mark.width * 0.33), round(mark.height * 0.23)),
    )
    bounds = canvas.getchannel("A").getbbox()
    if bounds is None:
        raise ValueError("A composicao final do icone ficou vazia.")
    return canvas.crop(bounds)


def create_icon(source_path: Path, size: int = MASTER_SIZE) -> Image.Image:
    if size <= 0:
        raise ValueError("O tamanho do icone deve ser positivo.")

    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    mark = _compose_colored_mark(source_path)
    target_width = max(1, round(size * MARK_WIDTH_RATIO))
    target_height = max(1, round(mark.height * target_width / mark.width))
    mark = mark.resize((target_width, target_height), Image.Resampling.LANCZOS)
    position = (
        round(size * MARK_LEFT_PADDING_RATIO),
        (size - target_height) // 2,
    )
    canvas.alpha_composite(mark, position)
    return canvas


def generate_assets(
    output_directory: Path = DEFAULT_OUTPUT,
    source_path: Path = DEFAULT_SOURCE,
) -> None:
    output_directory.mkdir(parents=True, exist_ok=True)
    master = create_icon(source_path)
    master.save(output_directory / "todox-icon.png", optimize=True)

    tray = master.resize((64, 64), Image.Resampling.LANCZOS)
    tray.save(output_directory / "todox-tray.png", optimize=True)

    master.save(
        output_directory / "todox.ico",
        format="ICO",
        sizes=[(size, size) for size in ICON_SIZES],
    )


def main() -> None:
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    source = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_SOURCE
    generate_assets(output.resolve(), source.resolve())


if __name__ == "__main__":
    main()
