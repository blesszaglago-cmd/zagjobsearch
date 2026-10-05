import unittest
from unittest.mock import AsyncMock, patch, MagicMock
from job_sources.himalayas import HimalayasClient

class HimalayasTests(unittest.IsolatedAsyncioTestCase):
    async def search_fixture(self, jobs):
        response = MagicMock()
        response.json.return_value = {"jobs": jobs}
        client = AsyncMock()
        client.get.return_value = response
        with patch("job_sources.himalayas.httpx.AsyncClient") as factory:
            factory.return_value.__aenter__.return_value = client
            result = await HimalayasClient().search("engineer", "GH")
            self.assertEqual(client.get.call_args.kwargs["params"]["country"], "GH")
            return result["jobs"]

    async def test_string_country_restrictions_are_not_worldwide(self):
        jobs = await self.search_fixture([{"guid": "1", "locationRestrictions": ["Ghana", "Nigeria"], "currency": "USD", "salaryPeriod": "yearly"}])
        self.assertEqual(jobs[0]["location"], "Ghana, Nigeria")
        self.assertEqual(jobs[0]["salary_currency"], "USD")
        self.assertEqual(jobs[0]["id"], "himalayas:1")

    async def test_expired_jobs_removed_and_live_jobs_retained(self):
        jobs = await self.search_fixture([{"guid": "old", "expiryDate": "2020-01-01T00:00:00Z"}, {"guid": "current", "expiryDate": "2099-01-01T00:00:00Z"}])
        self.assertEqual([job["id"] for job in jobs], ["himalayas:current"])

    async def test_legacy_dictionary_restrictions_remain_supported(self):
        jobs = await self.search_fixture([{"guid": "legacy", "locationRestrictions": [{"name": "Canada"}]}])
        self.assertEqual(jobs[0]["location"], "Canada")

if __name__ == "__main__":
    unittest.main()
