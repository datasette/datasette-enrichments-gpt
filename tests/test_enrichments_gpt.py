from datasette.app import Datasette
from datasette_test import actor_cookie
from datasette_enrichments.utils import wait_for_job
import os
import pytest


@pytest.mark.asyncio
@pytest.mark.vcr(ignore_localhost=True)
async def test_enrichments_gpt(monkeypatch):
    if not os.environ.get("DATASETTE_SECRETS_OPENAI_API_KEY"):
        monkeypatch.setenv("DATASETTE_SECRETS_OPENAI_API_KEY", "sk-xyz")
    ds = Datasette()
    db = ds.add_memory_database("test")
    await db.execute_write("create table museums (id integer primary key, name text)")
    await db.execute_write("insert into museums (name) values ('Hearst Castle')")
    cookies = {"ds_actor": actor_cookie(ds, {"id": "root"})}

    response1 = await ds.client.get("/-/enrich/test/museums/gpt", cookies=cookies)
    assert "<h2>AI analysis with OpenAI GPT</h2>" in response1.text

    # Now try and run it
    csrftoken = response1.cookies["ds_csrftoken"]
    cookies["ds_csrftoken"] = csrftoken

    response2 = await ds.client.post(
        "/-/enrich/test/museums/gpt",
        cookies=cookies,
        data={
            "model": "gpt-3.5-turbo",
            "prompt": "{{ name }}",
            "system_prompt": "haiku",
            "output_column": "haiku",
            "csrftoken": csrftoken,
        },
    )
    assert response2.status_code == 302
    job_id = response2.headers["location"].split("=")[-1]
    # Wait for it to finish
    await asyncio.sleep(0.1)
    await wait_for_job(ds, job_id, "test", timeout=10)
    # Should have no errors
    errors = [
        dict(row)
        for row in await db.execute(
            "select job_id, row_pks, error from _enrichment_errors"
        )
    ]
    assert errors == []
    # Check the result
    response3 = await ds.client.get("/test/museums.json?_shape=array")
    data = response3.json()
    assert data == [
        {
            "id": 1,
            "name": "Hearst Castle",
            "haiku": "Majestic atop\nCalifornia cliffs, Hearst Castle\nHistory whispers",
        }
    ]
