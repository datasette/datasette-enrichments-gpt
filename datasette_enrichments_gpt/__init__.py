from __future__ import annotations
from datasette_enrichments import Enrichment
from datasette_secrets import Secret
from datasette import hookimpl
from datasette.database import Database
import httpx
from typing import List, Optional
from wtforms import (
    Form,
    StringField,
    TextAreaField,
    BooleanField,
    SelectField,
)
from wtforms.validators import ValidationError, DataRequired
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
    secret = Secret(
        name="OPENAI_API_KEY",
        description="OpenAI API key",
        obtain_label="Get an OpenAI API key",
        obtain_url="https://platform.openai.com/api-keys",
    )

    async def get_config_form(self, datasette, db, table):
        columns = await db.table_columns(table)

        # Default template uses all string columns
        default = " ".join("{{ COL }}".replace("COL", col) for col in columns)

        url_columns = [col for col in columns if "url" in col.lower()]
        image_url_suggestion = ""
        if url_columns:
            image_url_suggestion = "{{ %s }}" % url_columns[0]

        class ConfigForm(Form):
            model = SelectField(
                "Model",
                choices=[
                    ("gpt-3.5-turbo", "gpt-3.5-turbo"),
                    ("gpt-4o", "gpt-4o"),
                    ("gpt-4o-vision", "gpt-4o vision"),
                ],
                default="gpt-3.5-turbo",
            )
            prompt = TextAreaField(
                "Prompt",
                description="A template to run against each row to generate a prompt. Use {{ COL }} for columns.",
                default=default,
                validators=[DataRequired(message="Prompt is required.")],
                render_kw={"style": "height: 8em"},
            )
            image_url = StringField(
                "Image URL",
                description="Image URL template. Only used with gpt-4o-vision.",
                default=image_url_suggestion,
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

        return ConfigForm

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
        body["max_tokens"] = 1000
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

    async def turbo_completion(
        self, api_key, model, prompt, system=None, json_format=False
    ) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return await self._chat_completion(
            api_key, model, messages, json_format=json_format
        )

    async def gpt4_vision(self, api_key, prompt, image_url, system=None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append(
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }
        )
        return await self._chat_completion(api_key, "gpt-4o", messages)

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
        api_key = await self.get_secret(datasette, config)
        if rows:
            row = rows[0]
        else:
            return
        prompt = config["prompt"] or ""
        system = config["system_prompt"] or None
        json_format = bool(config.get("json_format"))
        output_column = config["output_column"]
        image_url = config["image_url"]
        for key, value in row.items():
            prompt = prompt.replace("{{ %s }}" % key, str(value or "")).replace(
                "{{%s}}" % key, str(value or "")
            )
            if image_url:
                image_url = image_url.replace(
                    "{{ %s }}" % key, str(value or "")
                ).replace("{{%s}}" % key, str(value or ""))
        model = config["model"]
        if model == "gpt-4o-vision":
            output = await self.gpt4_vision(api_key, prompt, image_url, system)
        else:
            output = await self.turbo_completion(
                api_key, model, prompt, system, json_format
            )
        await db.execute_write(
            "update [{table}] set [{output_column}] = ? where {wheres}".format(
                table=table,
                output_column=output_column,
                wheres=" and ".join('"{}" = ?'.format(pk) for pk in pks),
            ),
            [output] + list(row[pk] for pk in pks),
        )
