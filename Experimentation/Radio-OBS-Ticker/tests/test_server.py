import unittest

import server


class ReconcileMetadataTests(unittest.TestCase):
    def test_reconcile_metadata_returns_comment_for_matching_titles(self) -> None:
        payload = server.reconcile_metadata(
            {"track_id": "track-123", "title": "Signal Fire"},
            {
                "title": "Signal Fire",
                "artist": "lunamidori",
                "comment": "Safe to display.",
            },
        )

        self.assertEqual(payload["track_id"], "track-123")
        self.assertEqual(payload["current_title"], "Signal Fire")
        self.assertEqual(payload["metadata_title"], "Signal Fire")
        self.assertEqual(payload["artist"], "lunamidori")
        self.assertEqual(payload["comment"], "Safe to display.")
        self.assertTrue(payload["matched"])

    def test_reconcile_metadata_matches_case_and_whitespace_variants(self) -> None:
        payload = server.reconcile_metadata(
            {"track_id": "track-123", "title": "De Pie Otra Vez"},
            {
                "title": "  de   pie otra vez  ",
                "artist": "lunamidori",
                "comment": "Normalized titles still match.",
            },
        )

        self.assertEqual(payload["comment"], "Normalized titles still match.")
        self.assertTrue(payload["matched"])

    def test_reconcile_metadata_clears_comment_for_mismatch(self) -> None:
        payload = server.reconcile_metadata(
            {"track_id": "track-123", "title": "Signal Fire"},
            {
                "title": "Other Track",
                "artist": "lunamidori",
                "comment": "Should not be shown.",
            },
        )

        self.assertEqual(payload["comment"], "")
        self.assertFalse(payload["matched"])

    def test_reconcile_metadata_clears_comment_when_title_missing(self) -> None:
        payload = server.reconcile_metadata(
            {"track_id": "track-123", "title": ""},
            {
                "title": "Signal Fire",
                "artist": "lunamidori",
                "comment": "Should not be shown.",
            },
        )

        self.assertEqual(payload["comment"], "")
        self.assertFalse(payload["matched"])


class ApiMetadataTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.original_cache = dict(server.metadata_cache)

    async def asyncTearDown(self) -> None:
        async with server.metadata_lock:
            server.metadata_cache.clear()
            server.metadata_cache.update(self.original_cache)

    async def test_api_metadata_returns_safe_payload(self) -> None:
        async with server.metadata_lock:
            server.metadata_cache.clear()
            server.metadata_cache.update(
                server.reconcile_metadata(
                    {"track_id": "track-123", "title": "Signal Fire"},
                    {
                        "title": "Other Track",
                        "artist": "lunamidori",
                        "comment": "Should not be shown.",
                    },
                )
            )

        client = server.app.test_client()
        response = await client.get("/api/metadata")
        data = await response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["ok"])
        self.assertEqual(data["track_id"], "track-123")
        self.assertEqual(data["current_title"], "Signal Fire")
        self.assertEqual(data["metadata_title"], "Other Track")
        self.assertEqual(data["artist"], "lunamidori")
        self.assertEqual(data["comment"], "")
        self.assertFalse(data["matched"])
