"""PNG 导出：Pillow 写出，支持透明背景选项。"""

from __future__ import annotations

from PIL import Image


class PNGExporter:
    @staticmethod
    def write(
        image: Image.Image,
        path: str,
        transparent: bool = False,
    ) -> Image.Image:
        if transparent:
            image = image.convert("RGBA")
        else:
            rgba = image.convert("RGBA")
            bg = Image.new("RGB", rgba.size, (255, 255, 255))
            bg.paste(rgba, mask=rgba.getchannel("A"))
            image = bg
        image.save(path, format="PNG")
        return image
