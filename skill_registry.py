import re
import yaml
from pathlib import Path
from typing import Dict, List, Optional


PROJECT_ROOT = Path(__file__).parent.resolve()


class Skill:
    def __init__(self, name: str, description: str, skill_dir: Path):
        self.name = name
        self.description = description
        self.skill_dir = skill_dir
        self._full_content = None
        self._references = None

    def get_full_content(self) -> str:
        if self._full_content is None:
            skill_md = self.skill_dir / "SKILL.md"
            if skill_md.exists():
                self._full_content = skill_md.read_text(encoding="utf-8")
            else:
                self._full_content = ""
        return self._full_content

    def get_references(self) -> Dict[str, str]:
        if self._references is None:
            self._references = {}
            ref_dir = self.skill_dir / "references"
            if ref_dir.exists():
                for f in ref_dir.glob("**/*"):
                    if f.is_file():
                        rel_path = str(f.relative_to(ref_dir))
                        try:
                            self._references[rel_path] = f.read_text(encoding="utf-8")
                        except Exception:
                            self._references[rel_path] = f"[Binary file: {rel_path}]"
        return self._references

    def has_scripts(self) -> bool:
        scripts_dir = self.skill_dir / "scripts"
        return scripts_dir.exists() and any(scripts_dir.iterdir())

    def has_references(self) -> bool:
        ref_dir = self.skill_dir / "references"
        return ref_dir.exists() and any(ref_dir.iterdir())

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "has_scripts": self.has_scripts(),
            "has_references": self.has_references()
        }


class SkillRegistry:
    def __init__(self, skills_dir: str = None):
        self.skills_dir = Path(skills_dir) if skills_dir else PROJECT_ROOT / "skills"
        self._skills: Dict[str, Skill] = {}
        self._initialized = False

    def discover_skills(self):
        if not self.skills_dir.exists():
            self.skills_dir.mkdir(parents=True, exist_ok=True)
            return

        for item in self.skills_dir.iterdir():
            if item.is_dir() and (item / "SKILL.md").exists():
                self._register_skill(item)

        self._initialized = True

    def _parse_skill_md(self, skill_md_path: Path) -> tuple:
        content = skill_md_path.read_text(encoding="utf-8")

        frontmatter_match = re.match(
            r"^---\n(.*?)\n---\n(.*)$",
            content,
            re.DOTALL
        )

        if frontmatter_match:
            yaml_content = frontmatter_match.group(1)
            yaml_data = yaml.safe_load(yaml_content)

            name = yaml_data.get("name", skill_md_path.parent.name)
            description = yaml_data.get("description", "")

            return name, description

        name = skill_md_path.parent.name
        return name, ""

    def _register_skill(self, skill_dir: Path):
        skill_md = skill_dir / "SKILL.md"
        name, description = self._parse_skill_md(skill_md)

        skill = Skill(name, description, skill_dir)
        self._skills[name] = skill

    def get_skill(self, name: str) -> Optional[Skill]:
        return self._skills.get(name)

    def get_all_skills(self) -> List[Skill]:
        return list(self._skills.values())

    def reload(self):
        self._skills.clear()
        self._initialized = False
        self.discover_skills()

    def get_trigger_info(self) -> str:
        info = []
        for skill in self._skills.values():
            info.append(f'<skill name="{skill.name}" description="{skill.description}" />')
        return "\n".join(info)

    @property
    def is_initialized(self) -> bool:
        return self._initialized


skill_registry = SkillRegistry()
