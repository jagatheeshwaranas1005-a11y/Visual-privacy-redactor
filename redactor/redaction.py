from __future__ import annotations

from PIL import Image, ImageDraw, ImageFilter

from .drawing import _bbox_pixels


def blur_region(image: Image.Image, box: tuple[int, int, int, int], radius: int = 18) -> None:
    region = image.crop(box)
    region = region.filter(ImageFilter.GaussianBlur(radius=radius))
    image.paste(region, box)


def pixelate_region(
    image: Image.Image,
    box: tuple[int, int, int, int],
    block_size: int = 16,
) -> None:
    region = image.crop(box)
    small = region.resize(
        (max(1, region.width // block_size), max(1, region.height // block_size)),
        Image.Resampling.NEAREST,
    )
    region = small.resize(region.size, Image.Resampling.NEAREST)
    image.paste(region, box)


def blackout_region(image: Image.Image, box: tuple[int, int, int, int], color: str = "#000000") -> None:
    draw = ImageDraw.Draw(image)
    draw.rectangle(box, fill=color)


def redact_region(
    image: Image.Image,
    method: str,
    box: tuple[int, int, int, int],
    blur_radius: int = 18,
    block_size: int = 16,
) -> None:
    """Apply a single redaction method in place. box is (x1, y1, x2, y2)."""
    if method == "blur":
        blur_region(image, box, radius=blur_radius)
    elif method == "pixelate":
        pixelate_region(image, box, block_size=block_size)
    elif method == "blackout":
        blackout_region(image, box)
    else:
        raise ValueError(f"Unknown redaction method: {method}")


def redact_image(
    image: Image.Image,
    boxes: list[tuple[list[float], str]],
    blur_radius: int = 18,
    block_size: int = 16,
) -> Image.Image:
    """Apply redactions to a copy. boxes is [(bbox, method), ...]."""
    result = image.copy()
    width, height = result.size
    for bbox, method in boxes:
        px = _bbox_pixels(bbox, width, height)
        redact_region(result, method, px, blur_radius=blur_radius, block_size=block_size)
    return result