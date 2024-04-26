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

Once installed, this plugin will allow users to select rows to enrich and run them through prompts using `gpt-3.5-turbo` or `gpt-4-turbo`, saving the result of the prompt in the specified column.

The plugin also provides `gpt-4-turbo vision`, which can run prompts against an image identified by a URL.

### Estimate Cost Feature

The plugin now includes an "Estimate cost" feature, allowing users to get an estimated cost for their enrichment tasks before execution. This feature works by clicking the "Estimate cost" button available on the enrichment form. Upon clicking, the tool sends a request to the `/-/enrichments-gpt/estimate` API endpoint with the details of the enrichment task. The endpoint then calculates an estimated token count required for the task and returns this information to the user.

To use this feature, ensure your form includes the "Estimate cost" button and that your server is set up to handle requests to the `/-/enrichments-gpt/estimate` endpoint as described in the plugin documentation.

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
