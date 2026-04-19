"""Focus GFX Shine 생성 서비스."""

import re


class FocusGFXShineGenerator:
    """Focus GFX에 누락된 shine 항목을 추가한다."""

    def __init__(self):
        self.goal_regex = re.compile(
            r'name\s*=\s*"([^"]+)?"(?:[^}]*?)texturefile\s*=\s*"([^"]+)?"',
            re.MULTILINE | re.DOTALL | re.IGNORECASE,
        )
        self.goal_name_regex = re.compile(
            r'name\s*=\s*"([^"]+)?"',
            re.MULTILINE | re.DOTALL | re.IGNORECASE,
        )
        self.comments_regex = re.compile(r"#.*$", re.MULTILINE)

    def get_shine_definition(self, name, path):
        rel_path = path.replace("\\", "/")
        return (
            '\tSpriteType = {\n'
            f'\t\tname = "{name}_shine"\n'
            f'\t\ttexturefile = "{rel_path}"\n'
            '\t\teffectFile = "gfx/FX/buttonstate.lua"\n'
            '\t\tanimation = {\n'
            f'\t\t\tanimationmaskfile = "{rel_path}"\n'
            '\t\t\tanimationtexturefile = "gfx/interface/goals/shine_overlay.dds"\n'
            '\t\t\tanimationrotation = -90.0\n'
            '\t\t\tanimationlooping = no\n'
            '\t\t\tanimationtime = 0.75\n'
            '\t\t\tanimationdelay = 0\n'
            '\t\t\tanimationblendmode = "add"\n'
            '\t\t\tanimationtype = "scrolling"\n'
            '\t\t\tanimationrotationoffset = { x = 0.0 y = 0.0 }\n'
            '\t\t\tanimationtexturescale = { x = 1.0 y = 1.0 }\n'
            '\t\t}\n'
            '\n'
            '\t\tanimation = {\n'
            f'\t\t\tanimationmaskfile = "{rel_path}"\n'
            '\t\t\tanimationtexturefile = "gfx/interface/goals/shine_overlay.dds"\n'
            '\t\t\tanimationrotation = 90.0\n'
            '\t\t\tanimationlooping = no\n'
            '\t\t\tanimationtime = 0.75\n'
            '\t\t\tanimationdelay = 0\n'
            '\t\t\tanimationblendmode = "add"\n'
            '\t\t\tanimationtype = "scrolling"\n'
            '\t\t\tanimationrotationoffset = { x = 0.0 y = 0.0 }\n'
            '\t\t\tanimationtexturescale = { x = 1.0 y = 1.0 }\n'
            '\t\t}\n'
            '\t\tlegacy_lazy_load = no\n'
            '\t}'
        )

    def process_files(self, goals_file, goals_shine_file):
        try:
            with open(goals_shine_file, "r", encoding="utf-8") as f:
                goals_shine_content = f.read()

            goals_shine_matches = self.goal_name_regex.findall(
                self.comments_regex.sub("", goals_shine_content)
            )
            goals_shine_set = set(goals_shine_matches)

            last_bracket_idx = 0
            for i in range(len(goals_shine_content) - 1, -1, -1):
                if goals_shine_content[i] == "}":
                    last_bracket_idx = i
                    break

            goals_shine_split = [
                goals_shine_content[:last_bracket_idx],
                goals_shine_content[last_bracket_idx:],
            ]

            with open(goals_file, "r", encoding="utf-8") as f:
                goals_content = f.read()

            goals_matches = self.goal_regex.findall(
                self.comments_regex.sub("", goals_content)
            )

            missing_shine = {
                name: path
                for name, path in goals_matches
                if f"{name}_shine" not in goals_shine_set
            }

            added_count = 0
            for name, path in missing_shine.items():
                shine_def = self.get_shine_definition(name, path)
                goals_shine_split.insert(1, shine_def)
                added_count += 1

            if added_count > 0:
                with open(goals_shine_file, "w", encoding="utf-8") as f:
                    f.write("\n".join(goals_shine_split))

            return {
                "success": True,
                "added_count": added_count,
                "missing_shine": list(missing_shine.keys()),
            }

        except Exception as e:
            return {"success": False, "error": str(e)}
