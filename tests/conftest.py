"""Isolated HTTP fixtures for the unit suite; live checks run separately."""

import csv
import io
import json
import re
import zipfile
from urllib.parse import parse_qs, urlsplit

import pytest
import responses

from mobility_db_api.csv_catalog import CSVCatalog


@pytest.fixture(autouse=True)
def isolated_http_and_storage(monkeypatch, tmp_path):
    """Exercise real client code without credentials, live feeds or shared data."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MOBILITY_API_REFRESH_TOKEN", "test_refresh_token")
    base_url = "https://api.mobilitydatabase.org/v1"
    providers = {}
    archives = {}
    for provider_id in (
        "mdb-859",
        "mdb-2036",
        "mdb-685",
        "mdb-1860",
        "mdb-123",
        "tld-5862",
    ):
        url = f"https://downloads.example.test/{provider_id}.zip"
        providers[provider_id] = {
            "id": provider_id,
            "provider": f"Test Provider {provider_id}",
            "data_type": "gtfs",
            "status": "active",
            "locations": [{"country_code": "LU"}],
            "source_info": {"producer_url": url},
            "latest_dataset": {"id": f"{provider_id}-v1", "hosted_url": url},
        }
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr(
                "stops.txt",
                "stop_id,stop_name,stop_lat,stop_lon\n"
                "1,First Stop,42.737182450611,-124.17377849378\n"
                "2,Last Stop,43.695870028905,-123.01875661\n",
            )
            zf.writestr("routes.txt", f"route_id,route_short_name\n1,{provider_id}\n")
            zf.writestr(
                "feed_info.txt",
                "feed_publisher_name,feed_publisher_url,feed_lang,feed_start_date,feed_end_date\n"
                "Test Provider,https://example.test,en,20260101,20261231\n",
            )
        archives[url] = archive.getvalue()

    def token_response(request):
        """Return dummy credentials or the expected invalid-token response."""
        token = json.loads(request.body)["refresh_token"]
        if token == "invalid_token":
            return 401, {}, "{}"
        assert token in ("test_refresh_token", "mock_refresh_token")
        return 200, {}, json.dumps({"access_token": "mock_token"})

    def feed_response(request):
        """Look up a fixture feed by its exact API path ID."""
        provider_id = request.path_url.rsplit("/", 1)[-1]
        provider = providers.get(provider_id)
        return (200, {}, json.dumps(provider)) if provider else (404, {}, "{}")

    def search_response(request):
        """Filter fixture feeds by the requested country or provider name."""
        params = parse_qs(urlsplit(request.url).query)
        matches = list(providers.values())
        if "country_code" in params:
            matches = [
                p
                for p in matches
                if p["locations"][0]["country_code"] == params["country_code"][0]
            ]
        if "provider" in params:
            matches = [
                p
                for p in matches
                if params["provider"][0].lower() in p["provider"].lower()
            ]
        return 200, {}, json.dumps(matches)

    catalog = io.StringIO()
    writer = csv.writer(catalog)
    writer.writerow(
        [
            "id",
            "data_type",
            "provider",
            "location.country_code",
            "urls.latest",
            "urls.direct_download",
            "status",
        ]
    )
    for p in providers.values():
        writer.writerow(
            [
                p["id"],
                "gtfs",
                p["provider"],
                "LU",
                p["latest_dataset"]["hosted_url"],
                p["source_info"]["producer_url"],
                "active",
            ]
        )

    with responses.RequestsMock(assert_all_requests_are_fired=False) as http:
        http.add_callback(responses.POST, f"{base_url}/tokens", callback=token_response)
        http.add_callback(
            responses.GET, f"{base_url}/gtfs_feeds", callback=search_response
        )
        http.add_callback(
            responses.GET,
            re.compile(r"^https://api\.mobilitydatabase\.org/v1/gtfs_feeds/[^/?]+$"),
            callback=feed_response,
        )
        http.add(responses.GET, CSVCatalog.CATALOG_URL, body=catalog.getvalue())
        for url, content in archives.items():
            http.add(responses.GET, url, body=content)
        yield
