"""GFX 사용처 분석 서비스.

`analyze_mod_folder()`는 Qt 비의존 순수 함수이고,
`AnalysisWorker`는 UI 스레딩용 Qt 래퍼이다.
"""

import os
import re
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

_FILE_EXTENSIONS = ("*.txt", "*.gui", "*.mod", "*.pdx", "*.interface",
                    "*.gfx", "*.lua", "*.yml", "*.yaml")

_GFX_PATTERNS = [
    r'icon\s*=\s*(["\']?)([A-Za-z0-9_]+)\1',
    r'texture\s*=\s*(["\']?)([A-Za-z0-9_]+)\1',
    r'spriteType\s*=\s*(["\']?)([A-Za-z0-9_]+)\1',
    r'texturefile\s*=\s*(["\']?)([A-Za-z0-9_./\\]+)\1',
    r'sprite\s*=\s*(["\']?)([A-Za-z0-9_]+)\1',
    r'frame\s*=\s*(["\']?)([A-Za-z0-9_]+)\1',
    r'buttonType\s*=\s*\{[^}]*?quadTextureSprite\s*=\s*(["\']?)([A-Za-z0-9_]+)\1',
    r'iconType\s*=\s*\{[^}]*?spriteType\s*=\s*(["\']?)([A-Za-z0-9_]+)\1',
    r'instantTextBoxType\s*=\s*\{[^}]*?font\s*=\s*(["\']?)([A-Za-z0-9_]+)\1',
    r'GFX_[A-Za-z0-9_]+',
    r'"(GFX_[^"]+)"',
    r"'(GFX_[^']+)'",
    r'@\[?([A-Za-z0-9_]*GFX[A-Za-z0-9_]*)\]?',
    r'\$([A-Za-z0-9_]*GFX[A-Za-z0-9_]*)\$',
    r'@sprite\s*=\s*([A-Za-z0-9_]+)',
    r'@texture\s*=\s*([A-Za-z0-9_]+)',
    r'effectFile\s*=\s*(["\']?)([A-Za-z0-9_./\\]+)\1',
    r'animationmaskfile\s*=\s*(["\']?)([A-Za-z0-9_./\\]+)\1',
    r'animationtexturefile\s*=\s*(["\']?)([A-Za-z0-9_./\\]+)\1',
    r'GetSprite\s*\(\s*["\']([^"\'")]+)["\']\s*\)',
    r'SetSprite\s*\(\s*["\']([^"\'")]+)["\']\s*\)',
    r'background\s*=\s*(["\']?)([A-Za-z0-9_]+)\1',
    r'highlight\s*=\s*(["\']?)([A-Za-z0-9_]+)\1',
    r'glow\s*=\s*(["\']?)([A-Za-z0-9_]+)\1',
]

_COMPILED_PATTERNS = [
    re.compile(p, re.IGNORECASE | re.MULTILINE | re.DOTALL) for p in _GFX_PATTERNS
]


def _strip_line_comments(content: str) -> str:
    """라인별로 `#` 주석 제거. 문자열 내부의 `#`은 유지."""
    cleaned_lines = []
    for line in content.split("\n"):
        in_string = False
        quote_char = None
        out = []
        pos = 0
        while pos < len(line):
            char = line[pos]
            if not in_string and char == "#":
                break
            if char in ('"', "'") and (pos == 0 or line[pos - 1] != "\\"):
                if not in_string:
                    in_string = True
                    quote_char = char
                elif char == quote_char:
                    in_string = False
                    quote_char = None
            out.append(char)
            pos += 1
        cleaned_lines.append("".join(out))
    return "\n".join(cleaned_lines)


def _iter_code_files(mod_folder_path):
    for ext in _FILE_EXTENSIONS:
        yield from Path(mod_folder_path).rglob(ext)


def analyze_mod_folder(mod_folder_path, gfx_data, progress_callback=None):
    """모드 폴더 전체에서 GFX 참조를 분석한다.

    progress_callback이 주어지면 0~100 진행률로 호출된다.
    """
    results = {
        "orphaned_gfx": set(),
        "missing_definitions": set(),
        "duplicate_definitions": {},
        "used_gfx": set(),
        "usage_locations": {},
    }

    def emit(value):
        if progress_callback is not None:
            progress_callback(value)

    emit(10)

    # 중복 정의 검사
    name_to_files = {}
    for name, info in gfx_data.items():
        name_to_files.setdefault(name, []).append(info["file_source"])
    for name, files in name_to_files.items():
        if len(files) > 1:
            results["duplicate_definitions"][name] = files

    emit(30)

    code_files = list(_iter_code_files(mod_folder_path))
    total_files = max(len(code_files), 1)

    for index, code_file in enumerate(code_files):
        try:
            with open(code_file, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            print(f"코드 파일 {code_file} 읽기 오류: {e}")
            continue

        content = _strip_line_comments(content)
        found_gfx = set()

        for pattern in _COMPILED_PATTERNS:
            for match in pattern.findall(content):
                if isinstance(match, tuple):
                    match = next((m for m in match if m), "")
                if not match or not ("GFX" in match or match.startswith("GFX_")):
                    continue

                if "/" in match or "\\" in match:
                    filename = os.path.splitext(os.path.basename(match))[0]
                    if filename.startswith("GFX_") or "GFX" in filename:
                        match = filename
                    else:
                        continue

                match = match.strip("\"'")
                if not (match and match in gfx_data):
                    continue

                gfx_definition_file = gfx_data[match]["file_source"]
                if str(code_file) == gfx_definition_file:
                    continue

                found_gfx.add(match)
                results["used_gfx"].add(match)
                locations = results["usage_locations"].setdefault(match, [])
                if str(code_file) not in locations:
                    locations.append(str(code_file))

        if found_gfx:
            sample = list(found_gfx)[:5]
            suffix = "..." if len(found_gfx) > 5 else ""
            print(
                f"Found {len(found_gfx)} GFX references in "
                f"{code_file.name}: {', '.join(sample)}{suffix}"
            )

        if index % 10 == 0:
            emit(30 + int((index / total_files) * 50))

    emit(80)

    for gfx_name in gfx_data:
        if gfx_name in results["used_gfx"]:
            continue
        base_name = gfx_name.replace("GFX_", "") if gfx_name.startswith("GFX_") else gfx_name
        is_used = False
        for used_gfx in results["used_gfx"]:
            used_base = used_gfx.replace("GFX_", "") if used_gfx.startswith("GFX_") else used_gfx
            if base_name == used_base or gfx_name in used_gfx or used_gfx in gfx_name:
                is_used = True
                if used_gfx in results["usage_locations"]:
                    gfx_definition_file = gfx_data[gfx_name]["file_source"]
                    locations = results["usage_locations"].setdefault(gfx_name, [])
                    for usage_file in results["usage_locations"][used_gfx]:
                        if usage_file != gfx_definition_file and usage_file not in locations:
                            locations.append(usage_file)
                break
        if not is_used:
            results["orphaned_gfx"].add(gfx_name)

    for used_gfx in results["used_gfx"]:
        if used_gfx not in gfx_data:
            results["missing_definitions"].add(used_gfx)

    print("\n=== GFX 사용처 분석 완료 ===")
    print(f"전체 GFX: {len(gfx_data)}개")
    print(f"사용된 GFX: {len(results['used_gfx'])}개 (자기 파일 참조 제외)")
    print(f"미사용 GFX: {len(results['orphaned_gfx'])}개")
    print(f"검사된 파일: {len(code_files)}개")

    emit(100)
    results["code_files_count"] = len(code_files)
    return results


class AnalysisWorker(QThread):
    """분석을 백그라운드에서 실행하는 Qt 워커."""

    progress_updated = pyqtSignal(int)
    analysis_complete = pyqtSignal(dict)

    def __init__(self, mod_folder_path, gfx_data):
        super().__init__()
        self.mod_folder_path = mod_folder_path
        self.gfx_data = gfx_data

    def run(self):
        results = analyze_mod_folder(
            self.mod_folder_path,
            self.gfx_data,
            progress_callback=self.progress_updated.emit,
        )
        self.analysis_complete.emit(results)
