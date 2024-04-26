from datasette.app import Datasette
import pytest


@pytest.mark.asyncio
async def test_plugin_is_installed():
    datasette = Datasette(memory=True)
    response = await datasette.client.get("/-/plugins.json")
    assert response.status_code == 200
    installed_plugins = {p["name"] for p in response.json()}
    assert "datasette-enrichments-gpt" in installed_plugins

@pytest.mark.asyncio
async def test_estimate_endpoint():
    datasette = Datasette(memory=True)
    response = await datasette.client.post(
        "/-/enrichments-gpt/estimate",
        json={
            "template": "Test template",
            "system_prompt": "Test system prompt",
            "filter_querystring": "id=1",
            "model": "gpt-4"
        }
    )
    assert response.status_code == 200
    assert "estimated_tokens" in response.json()
    assert isinstance(response.json()["estimated_tokens"], int)
