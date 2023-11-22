# datasette-enrichments-gpt

[![PyPI](https://img.shields.io/pypi/v/datasette-enrichments-gpt.svg)](https://pypi.org/project/datasette-enrichments-gpt/)
[![Changelog](https://img.shields.io/github/v/release/datasette/datasette-enrichments-gpt?include_prereleases&label=changelog)](https://github.com/datasette/datasette-enrichments-gpt/releases)
[![Tests](https://github.com/datasette/datasette-enrichments-gpt/workflows/Test/badge.svg)](https://github.com/datasette/datasette-enrichments-gpt/actions?query=workflow%3ATest)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/datasette/datasette-enrichments-gpt/blob/main/LICENSE)

Datasette enrichment for analyzing row data using OpenAI's GPT models

## Installation

Install this plugin in the same environment as Datasette.
```bash
datasette install datasette-enrichments-gpt
```
## Configuration

This plugin needs an OpenAI API key. Configure that in `metadata.yml` like so
```yaml
plugins:
  datasette-enrichments-gpt:
    api_key: sk-..
```
Or to avoid that key being visible on `/-/metadata` set it as an environment variable and use this:
```yaml
plugins:
  datasette-enrichments-gpt:
    api_key:
      $env: OPENAI_API_KEY
```

## Usage

Once installed, this plugin will allow users to select rows to enrich and run them through prompts using `gpt-3.5-turbo`, saving the result of the prompt in the specified column.

## Development

To set up this plugin locally, first checkout the code. Then create a new virtual environment:
```bash
cd datasette-enrichments-gpt
python3 -m venv venv
source venv/bin/activate
```
Now install the dependencies and test dependencies:
```bash
pip install -e '.[test]'
```
To run the tests:
```bash
pytest
```
