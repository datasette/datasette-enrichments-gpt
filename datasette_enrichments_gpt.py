from __future__ import annotations
from datasette_enrichments import Enrichment
from datasette import hookimpl
from datasette.database import Database
import httpx
from typing import List, Optional
from wtforms import Form, StringField, TextAreaField
from wtforms.validators import DataRequired
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

    async def get_config_form(self, db, table):
        columns = await db.table_columns(table)

        # Default template uses all string columns
        default = " ".join("{{ COL }}".replace("COL", col) for col in columns)

        class ConfigForm(Form):
            prompt = TextAreaField(
                "Prompt",
                description="A template to run against each row to generate a prompt. Use {{ COL }} for columns.",
                default=default,
            )
            output_column = StringField(
                "Output column name",
                description="The column to store the output in - will be created if it does not exist.",
                validators=[DataRequired(message="Column is required.")],
                default="prompt_output",
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
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer {}".format(api_key),
                },
                json=body,
                timeout=60.0
            )
            response.raise_for_status()
            result = response.json()["choices"][0]["message"]["content"]
            # TODO: Record usage
            # usage = response["usage"]
            # completion_tokens, prompt_tokens
            return result

    async def gpt3_turbo(self, api_key, prompt, system=None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return await self._chat_completion(api_key, "gpt-3.5-turbo-1106", messages)

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
        plugin_config = datasette.plugin_config("datasette-enrichments-gpt")
        api_key = plugin_config["api_key"]
        if rows:
            row = rows[0]
        else:
            return
        print(pks)
        prompt = config["prompt"] or ""
        output_column = config["output_column"]
        for key, value in row.items():
            prompt = prompt.replace("{{ %s }}" % key, str(value or "")).replace(
                "{{%s}}" % key, str(value or "")
            )
        # Now run the prompt
        output = await self.gpt3_turbo(api_key, prompt)
        print([output] + list(row[pk] for pk in pks))
        await db.execute_write(
            "update [{table}] set [{output_column}] = ? where {wheres}".format(
                table=table,
                output_column=output_column,
                wheres=" and ".join('"{}" = ?'.format(pk) for pk in pks),
            ),
            [output] + list(row[pk] for pk in pks),
        )
