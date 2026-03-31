"""Integration tests: Vinmonopolet fetch pipeline."""

import json
from unittest.mock import patch

from fetch_vinmonopolet import main, transform_store


class TestVinmonopoletPipeline:
    """Full pipeline: mocked API → transformed output."""

    def test_transforms_multiple_stores(self, sample_api_store, sample_api_store_easter):
        """Multiple stores transform into valid output."""
        # Give stores different IDs
        store2 = {**sample_api_store_easter, "name": "100", "displayName": "Larvik"}
        store2["address"] = {**store2["address"], "town": "Larvik"}

        known = {"sandefjord", "larvik"}
        results = [
            transform_store(sample_api_store, {}, known),
            transform_store(store2, {}, known),
        ]

        assert len(results) == 2
        assert results[0]["municipality"] == "sandefjord"
        assert results[1]["municipality"] == "larvik"
        for r in results:
            assert "store_id" in r
            assert "standard_hours" in r
            assert "actual_hours" in r
            assert len(r["actual_hours"]) == 7

    def test_unmapped_stores_get_null_municipality(self, sample_api_store):
        """Stores in unknown towns get municipality=None."""
        store = {**sample_api_store}
        store["address"] = {**store["address"], "town": "Ukjentby"}
        result = transform_store(store, {}, {"sandefjord"})
        assert result["municipality"] is None


class TestVinmonopoletCLI:
    """Verify CLI entry point writes output."""

    @patch("fetch_vinmonopolet.fetch_all_stores")
    def test_writes_output_file(self, mock_fetch, sample_api_store, tmp_path):
        mock_fetch.return_value = [sample_api_store]

        # Set up tmp data dir with required files
        data_dir = tmp_path / "data"
        muni_dir = data_dir / "municipalities"
        muni_dir.mkdir(parents=True)
        (muni_dir / "sandefjord.json").write_text("{}")
        (data_dir / "town_municipality_map.json").write_text("{}")

        with patch(
            "sys.argv",
            ["prog", "--timeout", "10", "--page-size", "100", "--data-dir", str(data_dir)],
        ):
            main()

        output = data_dir / "generated" / "vinmonopolet.json"
        assert output.exists()
        with open(output, encoding="utf-8") as f:
            data = json.load(f)

        assert "metadata" in data
        assert "stores" in data
        assert data["metadata"]["total_stores"] == 1
        assert len(data["stores"]) == 1
        assert data["stores"][0]["store_id"] == "283"
        assert "window_start" in data["metadata"]
        assert "window_end" in data["metadata"]
        assert "fetched_at" in data["metadata"]
