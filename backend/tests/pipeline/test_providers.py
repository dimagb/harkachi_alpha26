import json

import httpx
import pytest

from app.config import get_settings
from app.integrations.registry import ProviderUnavailable


@pytest.mark.parametrize("status", [200, 403, 503])
def test_bureau_full_report_sends_consent_and_parses_or_fails(status, persona_data):
    from app.integrations.bureau import HttpBureauProvider

    persona = persona_data["personas"][0]
    payload = {"inn": persona["inn"], "kind": "FULL", **persona["bki"]}

    def handle(request):
        assert request.method == "POST"
        assert request.url.path.endswith("/bki/report")
        assert json.loads(request.content) == {
            "inn": persona["inn"],
            "kind": "FULL",
            "consent_id": "consent-123",
        }
        return httpx.Response(status, json=payload)

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        provider = HttpBureauProvider(client)
        if status == 200:
            report = provider.get(persona["inn"], "consent-123")
            assert report.model_dump() == payload
        else:
            with pytest.raises(ProviderUnavailable):
                provider.get(persona["inn"], "consent-123")


@pytest.mark.parametrize("status", [200, 403, 503])
def test_tax_check_parses_or_fails(status, persona_data):
    from app.integrations.tax import HttpTaxProvider

    persona = persona_data["personas"][0]
    payload = {"inn": persona["inn"], **persona["fns"]}

    def handle(request):
        assert str(request.url) == (
            f"{get_settings().mocks_url}/fns/check/{persona['inn']}"
        )
        return httpx.Response(status, json=payload)

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        provider = HttpTaxProvider(client)
        if status == 200:
            assert provider.get(persona["inn"]).model_dump() == payload
        else:
            with pytest.raises(ProviderUnavailable):
                provider.get(persona["inn"])
