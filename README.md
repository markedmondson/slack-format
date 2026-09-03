# slack-format

Format Markdown for clean pasting into Slack.

Agent output often contains headings, tables, task lists, and fenced code that do not survive a normal paste. `slack-format` converts those constructs into Slack-friendly markup while keeping compact tables aligned and turning wide tables into readable records.

## Requirements

- Python 3.9 or newer
- [Pandoc](https://pandoc.org/) available on `PATH`
- macOS `pbcopy` for the optional `--copy` flag

On macOS:

```sh
brew install pandoc pipx
```

## Install

The supported installation method is `pipx` directly from this repository:

```sh
pipx install git+https://github.com/markedmondson/slack-format.git
```

Upgrade to the latest commit (reinstall uses the original Git source):

```sh
pipx reinstall slack-format
```

Uninstall it:

```sh
pipx uninstall slack-format
```

### Work from a local clone

For development, install the checkout in editable mode:

```sh
git clone https://github.com/markedmondson/slack-format.git
cd slack-format
pipx install --editable .
```

The `slack-format` command now runs the code in that checkout, so a `git pull`
updates the next run. Uninstall the existing `slack-format` package first if you
are switching from the standard installation.

## Usage

Read a file:

```sh
slack-format message.md
```

Read stdin and copy the result:

```sh
some-agent-command | slack-format --copy
```

Choose the output target:

```sh
slack-format --target paste message.md
slack-format --target markdown message.md
slack-format --target api message.md
```

| Target | Intended use |
| --- | --- |
| `paste` | Manual paste into Slack with the **Format messages with markup** preference enabled. This is the default. |
| `markdown` | An integration that accepts standard Markdown. |
| `api` | Direct use with Slack Web API `mrkdwn` text. |

### Tables

Compact tables become aligned code blocks:

````text
Service  Owner  Status
-------  -----  ----------
API      Sam    Healthy
Worker   Jo     Needs work
````

Wide tables and tables containing links become records so they remain readable on narrow screens:

```text
*Service:* API
• *Owner:* Sam
• *Status:* Healthy
```

Use `--tables code` or `--tables records` to override the automatic choice. Change the automatic width threshold with `--table-width COLUMNS`.

Run `slack-format --help` for every option.

## Development

Run the tests against the source tree:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests
```

The tests invoke the installed Pandoc binary to catch incompatible AST changes.

## License

[MIT](LICENSE)

Slack is a trademark of Salesforce, Inc. This project is not affiliated with or endorsed by Slack or Salesforce.
