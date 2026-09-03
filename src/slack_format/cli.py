#!/usr/bin/env python3

import argparse
import json
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path


class SlackRenderer:
    def __init__(self, target="paste", table_style="auto", table_width=80):
        self.target = target
        self.table_style = table_style
        self.table_width = table_width

    def render(self, document):
        return self.blocks(document.get("blocks", [])).strip()

    def blocks(self, blocks):
        rendered = []
        previous_kind = None
        for block in blocks:
            part = self.block(block)
            if not part:
                continue
            kind = block["t"]
            separator = "\n" if kind == previous_kind and kind in ("BulletList", "OrderedList") else "\n\n"
            rendered.append((separator, part))
            previous_kind = kind

        output = ""
        for separator, part in rendered:
            output += (separator if output else "") + part
        return re.sub(r"\n{3,}", "\n\n", output.strip())

    def block(self, block):
        kind = block["t"]
        content = block.get("c")

        if kind in ("Para", "Plain"):
            return self.inlines(content)
        if kind == "Header":
            return self.bold(self.inlines(content[2]))
        if kind == "CodeBlock":
            code = self.text(content[1].rstrip())
            fence = self.code_fence(code)
            return f"{fence}\n{code}\n{fence}"
        if kind == "BlockQuote":
            quoted = self.blocks(content)
            return "\n".join(">" if not line else f"> {line}" for line in quoted.splitlines())
        if kind == "BulletList":
            return self.render_list(content, ordered=False)
        if kind == "OrderedList":
            return self.render_list(content[1], ordered=True, start=content[0][0])
        if kind == "HorizontalRule":
            return "--------------------------------"
        if kind == "Table":
            return self.render_table(content)
        if kind == "Div":
            return self.blocks(content[1])
        if kind == "LineBlock":
            return "\n".join(self.inlines(line) for line in content)
        if kind == "DefinitionList":
            return self.render_definitions(content)
        if kind == "RawBlock":
            return "" if content[0].lower() in ("html", "html5") else self.text(content[1])
        if kind == "Figure":
            return self.blocks(content[2])

        return ""

    def inlines(self, inlines):
        return "".join(self.inline(inline) for inline in inlines)

    def inline(self, inline):
        kind = inline["t"]
        content = inline.get("c")

        if kind == "Str":
            return self.text(content)
        if kind == "Space":
            return " "
        if kind in ("SoftBreak", "LineBreak"):
            return "\n"
        if kind == "Emph":
            return f"_{self.inlines(content)}_"
        if kind == "Strong":
            return self.bold(self.inlines(content))
        if kind == "Strikeout":
            marker = "~~" if self.target == "markdown" else "~"
            return f"{marker}{self.inlines(content)}{marker}"
        if kind in ("Superscript", "Subscript", "SmallCaps"):
            return self.inlines(content)
        if kind == "Quoted":
            quote = '"' if content[0]["t"] == "DoubleQuote" else "'"
            return f"{quote}{self.inlines(content[1])}{quote}"
        if kind == "Code":
            code = self.text(content[1])
            if self.target != "markdown" and "`" in code:
                return code
            fence = "`" * max(1, self.longest_backtick_run(code) + 1)
            padding = " " if code.startswith("`") or code.endswith("`") else ""
            return f"{fence}{padding}{code}{padding}{fence}"
        if kind == "Math":
            return self.text(content[1])
        if kind == "Link":
            label = self.inlines(content[1])
            url = content[2][0]
            return f"<{self.escape(url)}|{label}>" if self.target == "api" else f"[{label}]({url})"
        if kind == "Image":
            label = self.inlines(content[1]) or "Image"
            url = content[2][0]
            return f"<{self.escape(url)}|{label}>" if self.target == "api" else f"[{label}]({url})"
        if kind in ("Span", "Cite"):
            return self.inlines(content[1])
        if kind == "Note":
            return f" ({self.blocks(content)})"
        if kind == "RawInline":
            if content[0].lower() in ("html", "html5") and re.fullmatch(r"<br\s*/?>", content[1], re.IGNORECASE):
                return "\n"
            return "" if content[0].lower() in ("html", "html5") else self.text(content[1])

        return ""

    def render_list(self, items, ordered, start=1):
        output = []
        for index, item in enumerate(items):
            body = re.sub(r"\n\n(?=[•☑☐-]|\d+\.)", "\n", self.blocks(item))
            marker = f"{start + index}." if ordered else self.bullet()
            if not ordered and re.match(r"^[☒☑]\s", body):
                marker, body = ("- [x]" if self.target == "markdown" else "☑"), body[2:]
            elif not ordered and re.match(r"^☐\s", body):
                marker, body = ("- [ ]" if self.target == "markdown" else "☐"), body[2:]

            lines = body.splitlines() or [""]
            output.append(f"{marker} {lines[0]}")
            output.extend(f"  {line}" for line in lines[1:])
        return "\n".join(output)

    def render_definitions(self, definitions):
        output = []
        for term, descriptions in definitions:
            output.append(self.bold(self.inlines(term)))
            output.extend(self.blocks(description) for description in descriptions)
        return "\n".join(output)

    def render_table(self, table):
        rich_rows, plain_rows = self.table_rows(table)
        if not rich_rows:
            return ""

        code_table = self.code_table(plain_rows)
        has_links = any(re.search(r"\[[^]]+\]\([^)]+\)|<[^>|]+\|[^>]+>", cell) for row in rich_rows for cell in row)
        use_records = self.table_style == "records" or (
            self.table_style == "auto" and (has_links or self.display_width(code_table) > self.table_width)
        )

        if use_records:
            return self.record_table(rich_rows, plain_rows)

        code_table = self.escape(code_table) if self.target == "api" else code_table
        fence = self.code_fence(code_table)
        return f"{fence}\n{code_table}\n{fence}"

    def table_rows(self, table):
        header_rows = table[3][1]
        body_rows = []
        for body in table[4]:
            body_rows.extend(body[2])
            body_rows.extend(body[3])
        body_rows.extend(table[5][1])
        rows = header_rows + body_rows

        rich_rows = []
        plain_rows = []
        for row in rows:
            rich_row = []
            plain_row = []
            for cell in row[1]:
                rich_row.append(self.blocks(cell[4]).replace("\n", " / "))
                plain_row.append(self.plain_blocks(cell[4]).replace("\n", " / "))
            rich_rows.append(rich_row)
            plain_rows.append(plain_row)
        return rich_rows, plain_rows

    def code_table(self, rows):
        column_count = max(len(row) for row in rows)
        padded = [row + [""] * (column_count - len(row)) for row in rows]
        widths = [max(self.display_width(row[column]) for row in padded) for column in range(column_count)]

        def format_row(row):
            cells = [cell + " " * (widths[index] - self.display_width(cell)) for index, cell in enumerate(row)]
            return "  ".join(cells).rstrip()

        output = [format_row(padded[0]), "  ".join("-" * width for width in widths)]
        output.extend(format_row(row) for row in padded[1:])
        return "\n".join(output)

    def record_table(self, rich_rows, plain_rows):
        headings = plain_rows[0]
        output = []
        for index, row in enumerate(rich_rows[1:], start=1):
            if len(headings) == 1:
                heading = self.text(headings[0])
                value = row[0] if row else ""
                output.append(f"{self.bold(f'{heading}:')} {value}")
                continue

            title = row[0] if row and row[0] else f"Row {index}"
            first_heading = self.text(headings[0])
            details = [f"{self.bold(f'{first_heading}:')} {title}"]
            for column, heading in enumerate(headings[1:], start=1):
                value = row[column] if column < len(row) else ""
                escaped_heading = self.text(heading)
                details.append(f"{self.bullet()} {self.bold(f'{escaped_heading}:')} {value}")
            output.append("\n".join(details))
        return "\n\n".join(output)

    def plain_blocks(self, blocks):
        parts = []
        for block in blocks:
            kind = block["t"]
            content = block.get("c")
            if kind in ("Para", "Plain"):
                parts.append(self.plain_inlines(content))
            elif kind == "CodeBlock":
                parts.append(content[1])
            elif kind in ("BulletList", "OrderedList"):
                items = content if kind == "BulletList" else content[1]
                parts.extend(self.plain_blocks(item) for item in items)
            elif kind == "BlockQuote":
                parts.append(self.plain_blocks(content))
        return "\n".join(parts)

    def plain_inlines(self, inlines):
        output = []
        for inline in inlines:
            kind = inline["t"]
            content = inline.get("c")
            if kind == "Str":
                output.append(content)
            elif kind == "Space":
                output.append(" ")
            elif kind in ("SoftBreak", "LineBreak"):
                output.append("\n")
            elif kind in ("Emph", "Strong", "Strikeout", "Superscript", "Subscript", "SmallCaps"):
                output.append(self.plain_inlines(content))
            elif kind == "Quoted":
                output.append(self.plain_inlines(content[1]))
            elif kind in ("Code", "Math"):
                output.append(content[1])
            elif kind in ("Link", "Image"):
                label = self.plain_inlines(content[1])
                output.append(f"{label} ({content[2][0]})")
            elif kind in ("Span", "Cite"):
                output.append(self.plain_inlines(content[1]))
            elif kind == "RawInline" and content[0].lower() in ("html", "html5"):
                if re.fullmatch(r"<br\s*/?>", content[1], re.IGNORECASE):
                    output.append("\n")
        return "".join(output)

    def text(self, value):
        return self.escape(value) if self.target == "api" else value

    def bold(self, value):
        marker = "**" if self.target == "markdown" else "*"
        return f"{marker}{value}{marker}"

    def bullet(self):
        return "-" if self.target == "markdown" else "•"

    def code_fence(self, code):
        return "`" * max(3, self.longest_backtick_run(code) + 1)

    @staticmethod
    def longest_backtick_run(value):
        runs = re.findall(r"`+", value)
        return max((len(run) for run in runs), default=0)

    @staticmethod
    def escape(value):
        return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    @staticmethod
    def display_width(value):
        line_widths = []
        for line in value.splitlines() or [""]:
            width = 0
            for character in line:
                if unicodedata.combining(character):
                    continue
                width += 2 if unicodedata.east_asian_width(character) in ("W", "F") else 1
            line_widths.append(width)
        return max(line_widths)


def arguments():
    parser = argparse.ArgumentParser(
        prog="slack-format",
        description="Format Markdown for a Slack message. Reads stdin when FILE is omitted.",
        epilog="For manual paste, enable Slack's 'Format messages with markup' preference.",
    )
    parser.add_argument("file", nargs="?", help="Markdown file, or - for stdin")
    parser.add_argument(
        "--target",
        choices=("paste", "markdown", "api"),
        default="paste",
        help="paste for Slack markup, markdown for integrations, or api for raw mrkdwn",
    )
    parser.add_argument("--tables", choices=("auto", "code", "records"), default="auto")
    parser.add_argument("--table-width", type=int, default=80, metavar="COLUMNS")
    parser.add_argument("--copy", action="store_true", help="also copy the formatted text using pbcopy")
    return parser.parse_args()


def read_input(filename):
    if not filename or filename == "-":
        return sys.stdin.read()
    return Path(filename).read_text(encoding="utf-8")


def parse_markdown(markdown):
    pandoc = shutil.which("pandoc")
    if not pandoc:
        raise RuntimeError("pandoc is required (install it with: brew install pandoc)")
    result = subprocess.run(
        [pandoc, "--from=gfm", "--to=json"],
        input=markdown,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "pandoc could not parse the input")
    return json.loads(result.stdout)


def copy_to_clipboard(output):
    pbcopy = shutil.which("pbcopy")
    if not pbcopy:
        raise RuntimeError("pbcopy is not available on this system")
    result = subprocess.run([pbcopy], input=output, text=True, check=False)
    if result.returncode:
        raise RuntimeError("pbcopy failed")


def warn_if_long(output):
    length = len(output)
    if length > 40_000:
        print(
            f"slack-format: warning: output is {length:,} characters; Slack truncates messages above 40,000.",
            file=sys.stderr,
        )
    elif length > 4_000:
        print(
            f"slack-format: warning: output is {length:,} characters; Slack recommends 4,000 or fewer.",
            file=sys.stderr,
        )


def run():
    options = arguments()
    if options.table_width < 1:
        raise RuntimeError("--table-width must be positive")
    document = parse_markdown(read_input(options.file))
    output = SlackRenderer(options.target, options.tables, options.table_width).render(document)
    if options.copy:
        copy_to_clipboard(output)
    warn_if_long(output)
    print(output)


def main():
    try:
        run()
    except (OSError, RuntimeError, json.JSONDecodeError) as error:
        print(f"slack-format: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
