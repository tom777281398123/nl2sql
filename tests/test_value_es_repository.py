import unittest

from elasticsearch import NotFoundError

from backend.app.repositories.es.value_es_repository import ValueESRepository


class ValueESRepositoryTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_missing_index_has_actionable_error(self):
        class MissingIndexClient:
            async def search(self, **kwargs):
                raise NotFoundError("missing index", None, {})

        repository = ValueESRepository(MissingIndexClient())

        with self.assertRaisesRegex(RuntimeError, "./run.sh build-kb"):
            await repository.search("华东")

    async def test_search_maps_elasticsearch_documents_to_value_info(self):
        class SearchClient:
            async def search(self, **kwargs):
                return {
                    "hits": {
                        "hits": [
                            {
                                "_source": {
                                    "id": "dim_region.region_name.华东",
                                    "value": "华东",
                                    "column_id": "dim_region.region_name",
                                }
                            }
                        ]
                    }
                }

        repository = ValueESRepository(SearchClient())

        values = await repository.search("华东")

        self.assertEqual(values[0].id, "dim_region.region_name.华东")
        self.assertEqual(values[0].value, "华东")


if __name__ == "__main__":
    unittest.main()
