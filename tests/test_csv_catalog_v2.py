"""Regression coverage for MobilityData's current spreadsheet schema."""

import csv
import io
import json
import zipfile

import pytest
import responses

from mobility_db_api import MobilityAPI
from mobility_db_api.csv_catalog import CSVCatalog


@pytest.fixture
def v2_csv():
    """Build a V2 catalog with active feeds and excluded provider states."""
    output = io.StringIO()
    fields = [
        "id",
        "data_type",
        "provider",
        "name",
        "location.country_code",
        "urls.direct_download",
        "urls.latest",
        "urls.authentication_type",
        "urls.authentication_info",
        "urls.api_key_parameter_name",
        "location.bounding_box.minimum_latitude",
        "location.bounding_box.maximum_latitude",
        "location.bounding_box.minimum_longitude",
        "location.bounding_box.maximum_longitude",
        "status",
        "redirect.id",
    ]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for provider_id in ("mdb-123", "tld-5862", "tdg-81995"):
        writer.writerow(
            {
                "id": provider_id,
                "data_type": "gtfs",
                "provider": "Société de transport",
                "name": "Regional services",
                "location.country_code": "BE",
                "urls.direct_download": "https://example.test/direct.zip",
                "urls.latest": "https://example.test/latest.zip",
                "urls.authentication_type": "1",
                "urls.authentication_info": "https://example.test/auth",
                "urls.api_key_parameter_name": "api_key",
                "location.bounding_box.minimum_latitude": "49.5",
                "location.bounding_box.maximum_latitude": "51.5",
                "location.bounding_box.minimum_longitude": "2.5",
                "location.bounding_box.maximum_longitude": "6.5",
                "status": "active",
            }
        )
    for provider_id, data_type, status, redirect in (
        ("mdb-inactive", "gtfs", "inactive", ""),
        ("mdb-deprecated", "gtfs", "deprecated", ""),
        ("mdb-redirected", "gtfs", "active", "mdb-123"),
        ("mdb-realtime", "gtfs-rt", "active", ""),
    ):
        writer.writerow(
            {
                "id": provider_id,
                "data_type": data_type,
                "status": status,
                "redirect.id": redirect,
            }
        )
    return output.getvalue()


@responses.activate
def test_v2_search_ids_and_metadata(tmp_path, v2_csv):
    """Preserve V2 provider IDs and map current metadata fields."""
    responses.get(CSVCatalog.CATALOG_URL, body=v2_csv)
    api = MobilityAPI(data_dir=tmp_path, force_csv_mode=True)

    providers = api.get_providers_by_country("be")
    assert [p["id"] for p in providers] == ["mdb-123", "tld-5862", "tdg-81995"]
    assert api.get_providers_by_name("société") == providers
    assert api.get_provider_by_id("123")["id"] == "mdb-123"
    for provider in providers:
        assert api.get_provider_by_id(provider["id"]) == provider
        assert provider["feed_name"] == "Regional services"
        assert provider["external_ids"] == []
        assert provider["source_info"]["authentication_type"] == 1
        assert (
            provider["source_info"]["authentication_info_url"]
            == "https://example.test/auth"
        )
        assert provider["source_info"]["api_key_parameter_name"] == "api_key"
        assert provider["latest_dataset"]["id"].startswith(provider["id"] + "-")
        assert provider["latest_dataset"]["bounding_box"] == {
            "minimum_latitude": 49.5,
            "maximum_latitude": 51.5,
            "minimum_longitude": 2.5,
            "maximum_longitude": 6.5,
        }


@responses.activate
def test_default_client_falls_back_to_v2_without_a_token(monkeypatch, tmp_path, v2_csv):
    """Use the V2 catalog when no API token is configured."""
    monkeypatch.delenv("MOBILITY_API_REFRESH_TOKEN")
    responses.get(CSVCatalog.CATALOG_URL, body=v2_csv)
    api = MobilityAPI(data_dir=tmp_path)

    assert api._use_csv is True
    assert api.get_provider_by_id("tld-5862")["id"] == "tld-5862"
    assert len(responses.calls) == 1
    assert responses.calls[0].request.method == "GET"


@responses.activate
@pytest.mark.parametrize("use_direct_source", [False, True])
def test_v2_download_and_persist_metadata(tmp_path, v2_csv, use_direct_source):
    """Download either source and retain metadata across client reloads."""
    responses.get(CSVCatalog.CATALOG_URL, body=v2_csv)
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("stops.txt", "stop_id,stop_name\n1,Test Stop\n")
    url = (
        "https://example.test/direct.zip"
        if use_direct_source
        else "https://example.test/latest.zip"
    )
    responses.get(url, body=archive.getvalue())
    api = MobilityAPI(data_dir=tmp_path, force_csv_mode=True)

    path = api.download_latest_dataset("tdg-81995", use_direct_source=use_direct_source)
    assert path is not None and (path / "stops.txt").is_file()
    saved = json.loads(api.metadata_file.read_text())
    metadata = next(iter(saved.values()))
    assert metadata["provider_id"] == "tdg-81995"
    assert metadata["source_url"] == url
    assert metadata["is_direct_source"] == use_direct_source
    assert len(metadata["file_hash"]) == 64
    reloaded = MobilityAPI(data_dir=tmp_path, force_csv_mode=True)
    assert reloaded.list_downloaded_datasets()[0].download_path == path
    if not use_direct_source:
        assert metadata["minimum_latitude"] == 49.5


@responses.activate
def test_v2_cache_does_not_reuse_legacy_catalog(tmp_path, v2_csv):
    """Migrate to a separate V2 cache and reuse it offline."""
    legacy_path = tmp_path / "mobility_catalog.csv"
    legacy_csv = "mdb_source_id,data_type,provider\n999,gtfs,Old Provider\n"
    legacy_path.write_text(legacy_csv)
    responses.get("https://files.mobilitydatabase.org/feeds_v2.csv", body=v2_csv)
    catalog = CSVCatalog(cache_dir=tmp_path)

    assert catalog.get_provider_info("tdg-81995") is not None
    assert len(responses.calls) == 1
    assert legacy_path.read_text() == legacy_csv

    # A new client must still work offline after the V2 catalog is cached.
    responses.reset()
    offline = CSVCatalog(cache_dir=tmp_path)
    assert offline.get_provider_info("tdg-81995") is not None
    assert not responses.calls


@pytest.mark.parametrize("schema", ["v2", "legacy"])
@pytest.mark.parametrize(
    "invalid_key",
    [
        "minimum_latitude",
        "maximum_latitude",
        "minimum_longitude",
        "maximum_longitude",
    ],
)
def test_invalid_coordinates_preserve_catalog_rows(tmp_path, schema, invalid_key):
    """Keep both feed rows when one coordinate is nonnumeric or empty."""
    id_field = "id" if schema == "v2" else "mdb_source_id"
    prefix = "location.bounding_box." if schema == "v2" else "bounding_box."
    coordinates = {
        "minimum_latitude": "49.5",
        "maximum_latitude": "51.5",
        "minimum_longitude": "2.5",
        "maximum_longitude": "6.5",
    }
    fields = [id_field, "data_type", "status", "provider"] + [
        prefix + key for key in coordinates
    ]
    catalog = CSVCatalog(cache_dir=tmp_path)
    with catalog.csv_path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for number in (123, 456):
            row = {
                id_field: f"mdb-{number}" if schema == "v2" else str(number),
                "data_type": "gtfs",
                "status": "active",
                "provider": "Test Provider",
                **{prefix + key: value for key, value in coordinates.items()},
            }
            if number == 123:
                row[prefix + invalid_key] = "not-a-number"
                empty_key = next(key for key in coordinates if key != invalid_key)
                row[prefix + empty_key] = ""
            writer.writerow(row)

    providers = catalog.get_providers()
    assert [provider["id"] for provider in providers] == ["mdb-123", "mdb-456"]
    expected = {key: float(value) for key, value in coordinates.items()}
    assert providers[1]["latest_dataset"]["bounding_box"] == expected
    expected[invalid_key] = None
    expected[empty_key] = None
    assert providers[0]["latest_dataset"]["bounding_box"] == expected
    assert catalog.get_provider_info("mdb-123") == providers[0]
