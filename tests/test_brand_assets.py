import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.generate_brand_assets import (
    ICON_SIZES,
    MARK_LEFT_PADDING_RATIO,
    X_SCALE,
    create_icon,
    generate_assets,
)
from tools.generate_msix_assets import generate_assets as generate_msix_assets


PROJECT_DIRECTORY = Path(__file__).resolve().parents[1]
SOURCE_LOGO = PROJECT_DIRECTORY / "frontend" / "public" / "todox-logo-v2.png"


class BrandAssetsTest(unittest.TestCase):
    def test_msix_manifest_declares_a_transparent_background(self) -> None:
        manifest = (PROJECT_DIRECTORY / "msix" / "AppxManifest.xml").read_text(
            encoding="utf-8"
        )

        self.assertIn('BackgroundColor="transparent"', manifest)

    def test_icon_has_a_fully_transparent_background(self) -> None:
        icon = create_icon(SOURCE_LOGO, 64)

        self.assertEqual(icon.size, (64, 64))
        for position in ((0, 0), (63, 0), (0, 63), (63, 63), (3, 32)):
            with self.subTest(position=position):
                self.assertEqual(icon.getpixel(position)[3], 0)

    def test_icon_preserves_the_original_palette_and_enlarges_the_x(self) -> None:
        icon = create_icon(SOURCE_LOGO, 512)
        visible_pixels = [
            (red, green, blue)
            for red, green, blue, alpha in icon.get_flattened_data()
            if alpha > 200
        ]
        bright_purple = [
            color
            for color in visible_pixels
            if color[0] > 110 and color[1] > 35 and color[2] > 200
        ]
        dark_purple = [
            color
            for color in visible_pixels
            if color[0] < 110 and color[1] < 55 and 65 < color[2] < 200
        ]
        near_white = [
            color for color in visible_pixels if min(color) > 235
        ]

        self.assertGreater(X_SCALE, 1.0)
        self.assertGreater(len(bright_purple), 5_000)
        self.assertGreater(len(dark_purple), 2_000)
        self.assertEqual(near_white, [])

    def test_icon_has_extra_padding_on_the_left_of_the_mark(self) -> None:
        icon = create_icon(SOURCE_LOGO, 512)
        purple_mask = Image.new("L", icon.size, 0)
        purple_mask.putdata(
            [
                alpha
                if alpha > 80 and blue > 60 and red > green * 1.4
                else 0
                for red, green, blue, alpha in icon.get_flattened_data()
            ]
        )
        bounds = purple_mask.getbbox()

        self.assertIsNotNone(bounds)
        assert bounds is not None
        self.assertGreaterEqual(
            bounds[0],
            round(icon.width * MARK_LEFT_PADDING_RATIO) - 2,
        )

    def test_generates_png_and_multiresolution_ico(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            generate_assets(output, SOURCE_LOGO)

            with Image.open(output / "todox-icon.png") as icon:
                self.assertEqual(icon.size, (512, 512))
            with Image.open(output / "todox-tray.png") as tray:
                self.assertEqual(tray.size, (64, 64))
            with Image.open(output / "todox.ico") as windows_icon:
                self.assertEqual(
                    windows_icon.ico.sizes(),
                    {(size, size) for size in ICON_SIZES},
                )
                for size in ICON_SIZES:
                    with self.subTest(size=size):
                        layer = windows_icon.ico.getimage((size, size)).convert(
                            "RGBA"
                        )
                        self.assertEqual(layer.getpixel((0, 0))[3], 0)

    def test_generates_msix_assets_from_the_brand_icon(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            source = PROJECT_DIRECTORY / "assets" / "branding" / "todox-icon.png"

            generate_msix_assets(output, source)

            expected_sizes = {
                "StoreLogo.png": (50, 50),
                "Square44x44Logo.png": (44, 44),
                "Square150x150Logo.png": (150, 150),
                "Square310x310Logo.png": (310, 310),
                "Wide310x150Logo.png": (310, 150),
            }
            for filename, expected_size in expected_sizes.items():
                with self.subTest(filename=filename):
                    with Image.open(output / filename) as image:
                        self.assertEqual(image.size, expected_size)
                        self.assertEqual(image.mode, "RGBA")
                        self.assertEqual(image.getpixel((0, 0))[3], 0)
                        self.assertEqual(image.getchannel("A").getextrema(), (0, 255))


if __name__ == "__main__":
    unittest.main()
