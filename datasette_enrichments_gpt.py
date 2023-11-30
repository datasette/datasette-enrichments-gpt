from __future__ import annotations
from datasette_enrichments import Enrichment
from datasette import hookimpl
from datasette.database import Database
import httpx
from typing import List, Optional
from wtforms import Form, StringField, TextAreaField, BooleanField, PasswordField
from wtforms.validators import ValidationError, DataRequired
import secrets
import sqlite_utils


@hookimpl
def register_enrichments():
    return [GptEnrichment()]


class GptEnrichment(Enrichment):
    name = "AI analysis with OpenAI GPT"
    slug = "gpt"
    description = "Analyze data using OpenAI's GPT models"
    runs_in_process = True
    batch_size = 1

    async def get_config_form(self, datasette, db, table):
        columns = await db.table_columns(table)

        # Default template uses all string columns
        default = " ".join("{{ COL }}".replace("COL", col) for col in columns)

        class ConfigForm(Form):
            prompt = TextAreaField(
                "Prompt",
                description="A template to run against each row to generate a prompt. Use {{ COL }} for columns.",
                default=default,
                validators=[DataRequired(message="Prompt is required.")],
            )
            system_prompt = TextAreaField(
                "System prompt",
                description="Instructions to apply to the main prompt. Can only be a static string, no {{ columns }}",
                default="",
            )
            json_format = BooleanField(
                "JSON object",
                description="Output a valid JSON object {...} instead of plain text",
                default=False,
            )
            output_column = StringField(
                "Output column name",
                description="The column to store the output in - will be created if it does not exist.",
                validators=[DataRequired(message="Column is required.")],
                default="prompt_output",
            )

            def validate_prompt(self, field):
                if (
                    self.json_format.data
                    and "json" not in field.data.lower()
                    and "json" not in self.system_prompt.data.lower()
                ):
                    raise ValidationError(
                        'The prompt or system prompt must contain the word "JSON" when JSON format is selected.'
                    )

        def stash_api_key(form, field):
            if not (field.data or "").startswith("sk-"):
                raise ValidationError("API key must start with sk-")
            if not hasattr(datasette, "_enrichments_gpt_stashed_keys"):
                datasette._enrichments_gpt_stashed_keys = {}
            key = secrets.token_urlsafe(16)
            datasette._enrichments_gpt_stashed_keys[key] = field.data
            field.data = key

        class ConfigFormWithKey(ConfigForm):
            api_key = PasswordField(
                "API key",
                description="Your OpenAI API key",
                validators=[
                    DataRequired(message="API key is required."),
                    stash_api_key,
                ],
            )

        plugin_config = datasette.plugin_config("datasette-enrichments-gpt") or {}
        api_key = plugin_config.get("api_key")

        return ConfigForm if api_key else ConfigFormWithKey

    async def initialize(self, datasette, db, table, config):
        # Ensure column exists
        output_column = config["output_column"]

        def add_column_if_not_exists(conn):
            db = sqlite_utils.Database(conn)
            if output_column not in db[table].columns_dict:
                db[table].add_column(output_column, str)

        await db.execute_write_fn(add_column_if_not_exists)

    async def _chat_completion(
        self, api_key, model, messages, json_format=False
    ) -> str:
        body = {"model": model, "messages": messages}
        if json_format:
            body["response_format"] = {"type": "json_object"}
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer {}".format(api_key),
                },
                json=body,
                timeout=60.0,
            )
            response.raise_for_status()
            result = response.json()["choices"][0]["message"]["content"]
            # TODO: Record usage
            # usage = response["usage"]
            # completion_tokens, prompt_tokens
            return result

    async def gpt3_turbo(self, api_key, prompt, system=None, json_format=False) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return await self._chat_completion(
            api_key, "gpt-3.5-turbo-1106", messages, json_format=json_format
        )

    async def enrich_batch(
        self,
        datasette: "Datasette",
        db: Database,
        table: str,
        rows: List[dict],
        pks: List[str],
        config: dict,
        job_id: int,
    ) -> List[Optional[str]]:
        # API key should be in plugin settings OR pointed to by config
        api_key = resolve_api_key(datasette, config)
        if rows:
            row = rows[0]
        else:
            return
        prompt = config["prompt"] or ""
        system = config["system_prompt"] or None
        json_format = bool(config.get("json_format"))
        output_column = config["output_column"]
        for key, value in row.items():
            prompt = prompt.replace("{{ %s }}" % key, str(value or "")).replace(
                "{{%s}}" % key, str(value or "")
            )
        # Now run the prompt
        output = await self.gpt3_turbo(api_key, prompt, system, json_format)
        await db.execute_write(
            "update [{table}] set [{output_column}] = ? where {wheres}".format(
                table=table,
                output_column=output_column,
                wheres=" and ".join('"{}" = ?'.format(pk) for pk in pks),
            ),
            [output] + list(row[pk] for pk in pks),
        )


class ApiKeyError(Exception):
    pass


def resolve_api_key(datasette, config):
    plugin_config = datasette.plugin_config("datasette-enrichments-gpt") or {}
    api_key = plugin_config.get("api_key")
    if api_key:
        return api_key
    # Look for it in config
    api_key_name = config.get("api_key")
    if not api_key_name:
        raise ApiKeyError("No API key reference found in config")
    # Look it up in the stash
    if not hasattr(datasette, "_enrichments_gpt_stashed_keys"):
        raise ApiKeyError("No API key stash found")
    stashed_keys = datasette._enrichments_gpt_stashed_keys
    if api_key_name not in stashed_keys:
        raise ApiKeyError("No API key found in stash for {}".format(api_key_name))
    return stashed_keys[api_key_name]
