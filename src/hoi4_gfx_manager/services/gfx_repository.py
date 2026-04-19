"""GFX 파일 파싱/저장/수정 서비스 (Qt 비의존)."""

import os
import re
from pathlib import Path

_SPRITE_BLOCK = re.compile(
    r"spriteType\s*=\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}",
    re.DOTALL | re.IGNORECASE,
)
_NAME = re.compile(r'name\s*=\s*["\']?([^"\'}\s]+)["\']?', re.IGNORECASE)
_TEXTURE = re.compile(r'texturefile\s*=\s*["\']?([^"\'}\s]+)["\']?', re.IGNORECASE)


def _strip_comments(content: str) -> str:
    lines = []
    for line in content.split("\n"):
        if "#" in line:
            line = line[: line.index("#")]
        lines.append(line)
    return "\n".join(lines)


def parse_gfx_file(gfx_file_path, mod_folder_path):
    """단일 .gfx 파일에서 spriteType 블록을 파싱해 엔트리 리스트를 돌려준다.

    각 엔트리는 dict로 반환된다: name, texturefile(절대), relative_path, file_source.
    중복 여부/상태 판정은 호출 측에서 처리한다.
    """
    entries = []
    try:
        with open(gfx_file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError as e:
        raise RuntimeError(f"파일 {gfx_file_path} 읽기 실패: {e}") from e

    content = _strip_comments(content)

    for sprite_content in _SPRITE_BLOCK.findall(content):
        name_match = _NAME.search(sprite_content)
        texture_match = _TEXTURE.search(sprite_content)
        if not (name_match and texture_match):
            continue
        name = name_match.group(1).strip("\"'")
        texture_path = texture_match.group(1).strip("\"'")
        full_texture_path = os.path.join(mod_folder_path, texture_path)
        entries.append({
            "name": name,
            "texturefile": full_texture_path,
            "relative_path": texture_path,
            "file_source": str(gfx_file_path),
        })
    return entries


def scan_mod_folder(mod_folder_path):
    """모드 폴더의 모든 .gfx 파일을 스캔하여 (gfx_data, duplicates) 반환.

    gfx_data: {name: info_dict}
    duplicates: {name: [file_source, ...]}
    """
    gfx_data = {}
    duplicates = {}

    gfx_files = list(Path(mod_folder_path).rglob("*.gfx"))
    for gfx_file in gfx_files:
        try:
            entries = parse_gfx_file(gfx_file, mod_folder_path)
        except RuntimeError as e:
            print(e)
            continue

        for entry in entries:
            name = entry["name"]
            status = "valid" if os.path.exists(entry["texturefile"]) else "missing_file"

            if name in gfx_data:
                status = "duplicate"
                if name in duplicates:
                    duplicates[name].append(entry["file_source"])
                else:
                    duplicates[name] = [gfx_data[name]["file_source"], entry["file_source"]]

            gfx_data[name] = {
                "texturefile": entry["texturefile"],
                "file_source": entry["file_source"],
                "status": status,
                "relative_path": entry["relative_path"],
            }

    return gfx_data, duplicates, gfx_files


def save_gfx_to_file(gfx_file_path, name, relative_texture_path):
    """`.gfx` 파일에 새 spriteType 항목을 추가한다.

    상대 경로 정규화는 호출 측에서 수행해 넘긴다.
    """
    rel_path = relative_texture_path.replace("\\", "/")
    gfx_entry = (
        "\n\tspriteType = {"
        f'\n\t\tname = "{name}"'
        f'\n\t\ttexturefile = "{rel_path}"'
        "\n\t}"
    )

    with open(gfx_file_path, "r", encoding="utf-8") as f:
        content = f.read()

    if "spriteTypes = {" in content:
        last_brace = content.rfind("}")
        content = content[:last_brace] + gfx_entry + "\n" + content[last_brace:]
    else:
        content += f"\n\nspriteTypes = {{{gfx_entry}\n}}\n"

    with open(gfx_file_path, "w", encoding="utf-8") as f:
        f.write(content)


def remove_gfx_from_file(gfx_file_path, name):
    """`.gfx` 파일에서 지정된 spriteType 블록을 삭제한다."""
    with open(gfx_file_path, "r", encoding="utf-8") as f:
        content = f.read()

    pattern = rf'spriteType\s*=\s*\{{\s*name\s*=\s*["\']?{re.escape(name)}["\']?[^}}]*\}}'
    content = re.sub(pattern, "", content, flags=re.DOTALL)

    with open(gfx_file_path, "w", encoding="utf-8") as f:
        f.write(content)


def update_gfx_texture_path(gfx_file_path, name, new_relative_path):
    """기존 spriteType의 texturefile만 교체한다."""
    with open(gfx_file_path, "r", encoding="utf-8") as f:
        content = f.read()

    rel_new_path = new_relative_path.replace("\\", "/")
    pattern = rf'({re.escape(name)}\s*=\s*\{{[^}}]*?)texturefile\s*=\s*"[^"]*"'
    replacement = rf'\1texturefile = "{rel_new_path}"'
    content = re.sub(pattern, replacement, content, flags=re.DOTALL | re.MULTILINE | re.IGNORECASE)

    with open(gfx_file_path, "w", encoding="utf-8") as f:
        f.write(content)
