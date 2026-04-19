"""이미지 변환 서비스 (Qt 비의존)."""

from pathlib import Path

import cv2
import numpy as np
from PIL import Image

try:  # pragma: no cover - DDS 플러그인은 선택적
    from PIL import DdsImagePlugin  # noqa: F401
except ImportError:
    pass


class ImageConverter:
    """이미지 일괄 변환 클래스."""

    DDS_MAGIC = b"DDS "

    DDS_FORMATS = {
        "B8G8R8A8 (Linear, A8R8G8B8)": "RGBA",
        "DXT1 (BC1)": "DXT1",
        "DXT3 (BC2)": "DXT3",
        "DXT5 (BC3)": "DXT5",
        "BC7": "BC7",
        "R8G8B8": "RGB",
        "R8G8B8A8": "RGBA",
    }

    def __init__(self):
        self.supported_input = [".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tga"]
        self.supported_output = [".png", ".jpg", ".jpeg", ".bmp", ".dds"]

    def convert_image(self, input_path, output_path, output_format="PNG", dds_format="RGBA", quality=95):
        """단일 이미지를 지정된 포맷으로 변환."""
        try:
            with Image.open(input_path) as img:
                if img.mode in ("RGBA", "LA") or "transparency" in img.info:
                    if output_format.upper() == "DDS":
                        if img.mode != "RGBA":
                            img = img.convert("RGBA")
                    elif output_format.upper() in ["JPG", "JPEG"]:
                        background = Image.new("RGB", img.size, (255, 255, 255))
                        if img.mode == "RGBA":
                            background.paste(img, mask=img.split()[3])
                        else:
                            background.paste(img)
                        img = background
                    else:
                        if img.mode != "RGBA":
                            img = img.convert("RGBA")
                else:
                    if output_format.upper() == "DDS" and dds_format in ["RGBA", "DXT3", "DXT5"]:
                        img = img.convert("RGBA")
                    elif output_format.upper() in ["JPG", "JPEG"]:
                        img = img.convert("RGB")

                if output_format.upper() == "DDS":
                    self._save_as_dds(img, output_path, dds_format)
                else:
                    save_kwargs = {}
                    if output_format.upper() in ["JPG", "JPEG"]:
                        save_kwargs["quality"] = quality
                        save_kwargs["optimize"] = True
                    elif output_format.upper() == "PNG":
                        save_kwargs["optimize"] = True

                    img.save(output_path, format=output_format.upper(), **save_kwargs)

                return True, None

        except Exception as e:
            return False, str(e)

    def _save_as_dds(self, img, output_path, dds_format):
        """OpenCV로 DDS 저장 후 매직 헤더 검증."""
        try:
            if img.mode == "RGBA":
                img_array = np.array(img)
                img_bgra = cv2.cvtColor(img_array, cv2.COLOR_RGBA2BGRA)
            else:
                img_array = np.array(img.convert("RGB"))
                img_bgra = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

            success = cv2.imwrite(output_path, img_bgra)
            if not success:
                raise RuntimeError(f"OpenCV failed to write DDS data for '{dds_format}'.")

            with open(output_path, "rb") as dds_file:
                if dds_file.read(4) != self.DDS_MAGIC:
                    raise RuntimeError(
                        f"DDS conversion produced non-DDS data for '{dds_format}'."
                    )
        except Exception as e:
            try:
                Path(output_path).unlink(missing_ok=True)
            except OSError:
                pass
            raise RuntimeError(f"DDS conversion failed: {e}") from e

    def batch_convert(self, file_list, output_dir, output_format="PNG", dds_format="RGBA", quality=95):
        """파일 목록을 일괄 변환."""
        results = []

        for input_file in file_list:
            try:
                input_path = Path(input_file)
                output_filename = input_path.stem + "." + output_format.lower()
                output_path = Path(output_dir) / output_filename

                success, error = self.convert_image(
                    str(input_path), str(output_path), output_format, dds_format, quality
                )

                results.append({
                    "input": str(input_path),
                    "output": str(output_path),
                    "success": success,
                    "error": error,
                })

            except Exception as e:
                results.append({
                    "input": str(input_file),
                    "output": "",
                    "success": False,
                    "error": str(e),
                })

        return results
