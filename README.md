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

```sh
pipx install git+https://github.com/markedmondson/slack-format.git
```

To install from a local clone:

```sh
pipx install .
```

## Usage

Report the installed version:

```sh
slack-format --version
```

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

### Release

After the version change has merged and CI passes, create the matching tag and GitHub release from `main`:

```sh
git switch main
git pull --ff-only
git tag -a v0.1.0 -m "v0.1.0"
git push origin v0.1.0
gh release create v0.1.0 --generate-notes
```

## License

[MIT](LICENSE)

Slack is a trademark of Salesforce, Inc. This project is not affiliated with or endorsed by Slack or Salesforce.
