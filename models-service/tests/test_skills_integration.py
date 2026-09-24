"""Tests for skills integration — directory structure + model_service injection."""

import os
import sys
import unittest

# Add models-service root to path so we can import app modules
MODELS_SERVICE_DIR = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, MODELS_SERVICE_DIR)

# API_KEY is required by app.core.config.Settings — provide a dummy value.
os.environ.setdefault("API_KEY", "test-dummy-key")

SKILLS_DIR = os.path.join(MODELS_SERVICE_DIR, "skills")
SALES_SKILL_DIR = os.path.join(SKILLS_DIR, "sales-conversion")
RESOURCES_DIR = os.path.join(SALES_SKILL_DIR, "resources")


class TestSkillsDirectoryStructure(unittest.TestCase):
    """Verify the skills directory tree is present and correct."""

    def test_skills_directory_exists(self):
        """skills/ directory exists under models-service."""
        self.assertTrue(
            os.path.isdir(SKILLS_DIR),
            f"Expected directory at {SKILLS_DIR}",
        )

    def test_sales_conversion_directory_exists(self):
        """skills/sales-conversion/ directory exists."""
        self.assertTrue(
            os.path.isdir(SALES_SKILL_DIR),
            f"Expected directory at {SALES_SKILL_DIR}",
        )

    def test_skill_md_file_present(self):
        """SKILL.md exists in sales-conversion directory."""
        skill_md = os.path.join(SALES_SKILL_DIR, "SKILL.md")
        self.assertTrue(
            os.path.exists(skill_md),
            f"Missing SKILL.md at {skill_md}",
        )

    def test_all_resource_files_present(self):
        """All 5 resource markdown files are present."""
        expected_files = [
            "01-opening.md",
            "02-discovery.md",
            "03-support.md",
            "04-objection-handling.md",
            "05-closing.md",
        ]
        for fname in expected_files:
            path = os.path.join(RESOURCES_DIR, fname)
            self.assertTrue(
                os.path.exists(path),
                f"Missing resource file: {fname} (expected at {path})",
            )

    def test_skill_md_content_has_metadata(self):
        """SKILL.md contains expected YAML frontmatter with name: sales-conversion."""
        skill_md = os.path.join(SALES_SKILL_DIR, "SKILL.md")
        with open(skill_md) as f:
            content = f.read()
        self.assertIn("name: sales-conversion", content)
        self.assertIn("description:", content)

    def test_skill_md_references_view_text_file(self):
        """SKILL.md references view_text_file instead of read_skill_resource."""
        skill_md = os.path.join(SALES_SKILL_DIR, "SKILL.md")
        with open(skill_md) as f:
            content = f.read()
        self.assertIn("view_text_file", content)
        self.assertNotIn("read_skill_resource", content)


class TestModelServiceUserIdInjection(unittest.TestCase):
    """Verify _inject_runtime_user_id adds runtime constraint."""

    def test_injects_user_id_constraint(self):
        """_inject_runtime_user_id appends RUNTIME TOOL CONSTRAINT block."""
        from app.services.model_service import _inject_runtime_user_id

        base_prompt = "You are a helpful assistant."
        result = _inject_runtime_user_id(base_prompt, "test_user_123")

        self.assertIn("test_user_123", result)
        self.assertIn("RUNTIME TOOL CONSTRAINT", result)

    def test_injects_user_id_exactly(self):
        """The runtime user_id is injected verbatim."""
        from app.services.model_service import _inject_runtime_user_id

        result = _inject_runtime_user_id("prompt", "zalo_abc_789")
        self.assertIn("zalo_abc_789", result)

    def test_original_prompt_preserved(self):
        """The original system prompt text is preserved at the start."""
        from app.services.model_service import _inject_runtime_user_id

        base = "Original system prompt content here."
        result = _inject_runtime_user_id(base, "u1")
        self.assertTrue(result.startswith(base))


if __name__ == "__main__":
    unittest.main()
