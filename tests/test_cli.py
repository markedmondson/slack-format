import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from slack_format import __version__
from slack_format.cli import SlackRenderer, parse_markdown


PANDOC_AVAILABLE = shutil.which("pandoc") is not None
PROJECT_ROOT = Path(__file__).resolve().parents[1]


class VersionTest(unittest.TestCase):
    def test_reports_package_version(self):
        command = [sys.executable, "-m", "slack_format.cli", "--version"]
        command_env = os.environ.copy()
        command_env["PYTHONPATH"] = str(PROJECT_ROOT / "src")

        result = subprocess.run(command, text=True, capture_output=True, env=command_env, check=False)

        self.assertEqual(0, result.returncode)
        self.assertEqual(f"slack-format {__version__}\n", result.stdout)
        self.assertEqual("", result.stderr)


@unittest.skipUnless(PANDOC_AVAILABLE, "pandoc is required")
class RendererTest(unittest.TestCase):
    def render(self, markdown, **options):
        return SlackRenderer(**options).render(parse_markdown(markdown))

    def test_formats_common_blocks_for_paste(self):
        markdown = """# Status

**Ready**, but *careful* with ~~old~~ `flags`.

> Keep this visible.

- first
- [x] shipped
- [ ] announce
"""

        self.assertEqual(
            """*Status*

*Ready*, but _careful_ with ~old~ `flags`.

> Keep this visible.

• first
☑ shipped
☐ announce""",
            self.render(markdown),
        )

    def test_formats_standard_markdown_for_integrations(self):
        markdown = "# Status\n\n- one\n- [x] shipped\n\n~~gone~~\n"

        self.assertEqual(
            "**Status**\n\n- one\n- [x] shipped\n\n~~gone~~",
            self.render(markdown, target="markdown"),
        )

    def test_escapes_and_formats_links_for_the_api(self):
        markdown = "A < B & read [the guide](https://example.com/docs?a=1&b=2)."

        self.assertEqual(
            "A &lt; B &amp; read <https://example.com/docs?a=1&amp;b=2|the guide>.",
            self.render(markdown, target="api"),
        )

    def test_renders_a_compact_table_as_aligned_code(self):
        markdown = """| Item | Result |
| --- | --- |
| Search | Good |
| Worker | Needs work |
"""

        self.assertEqual(
            """```
Item    Result
------  ----------
Search  Good
Worker  Needs work
```""",
            self.render(markdown),
        )

    def test_renders_a_wide_table_without_losing_headings(self):
        markdown = """| Service | Owner | Status |
| --- | --- | --- |
| API | Sam | A deliberately long status for a narrow message |
"""

        self.assertEqual(
            """*Service:* API
• *Owner:* Sam
• *Status:* A deliberately long status for a narrow message""",
            self.render(markdown, table_width=30),
        )

    def test_preserves_breaks_and_wide_characters_in_tables(self):
        markdown = """| Name | Detail |
| --- | --- |
| 日本語 | first<br>second |
"""

        self.assertIn("日本語", self.render(markdown))
        self.assertIn("first / second", self.render(markdown))

    def test_uses_a_longer_fence_for_nested_backticks(self):
        markdown = "````\nbefore\n```\nafter\n````\n"

        self.assertEqual("````\nbefore\n```\nafter\n````", self.render(markdown))


@unittest.skipUnless(PANDOC_AVAILABLE, "pandoc is required")
class CommandTest(unittest.TestCase):
    def run_command(self, *arguments, input_text="", env=None):
        command = [sys.executable, "-m", "slack_format.cli", *arguments]
        command_env = os.environ.copy()
        command_env["PYTHONPATH"] = str(PROJECT_ROOT / "src")
        if env:
            command_env.update(env)
        return subprocess.run(command, input=input_text, text=True, capture_output=True, env=command_env, check=False)

    def test_reads_stdin(self):
        result = self.run_command(input_text="# Status\n")

        self.assertEqual(0, result.returncode)
        self.assertEqual("*Status*\n", result.stdout)
        self.assertEqual("", result.stderr)

    def test_reads_a_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "message.md"
            path.write_text("## Result\n", encoding="utf-8")

            result = self.run_command(str(path))

        self.assertEqual(0, result.returncode)
        self.assertEqual("*Result*\n", result.stdout)

    def test_rejects_a_non_positive_table_width(self):
        result = self.run_command("--table-width", "0", input_text="hello")

        self.assertEqual(1, result.returncode)
        self.assertIn("--table-width must be positive", result.stderr)

    def test_copies_with_pbcopy(self):
        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            copied_path = directory_path / "copied.txt"
            fake_pbcopy = directory_path / "pbcopy"
            fake_pbcopy.write_text(f"#!/bin/sh\nexec /usr/bin/tee '{copied_path}' >/dev/null\n", encoding="utf-8")
            fake_pbcopy.chmod(0o755)
            env = {"PATH": f"{directory}{os.pathsep}{os.environ['PATH']}"}

            result = self.run_command("--copy", input_text="**Ready**", env=env)

            self.assertEqual(0, result.returncode)
            self.assertEqual("*Ready*", copied_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
