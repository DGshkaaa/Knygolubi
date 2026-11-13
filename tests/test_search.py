"""Search regressions: punctuation must be treated literally, not as regex."""
import re
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from fastapi import Response
from app.api.books import list_books

class SearchTests(unittest.IsolatedAsyncioTestCase):
    async def test_literal_search_and_pagination(self):
        books = MagicMock()
        books.count_documents = AsyncMock(return_value=11)
        cursor = MagicMock()
        cursor.__aiter__.return_value = []
        books.find.return_value.skip.return_value.limit.return_value = cursor
        for search in ('C++', '[', '.*', '  Книга (том 1)  ', '   '):
            response = Response()
            await list_books(response, search=search, genre=None, availability=None,
                             sort_by=None, page=2, page_size=5, database=SimpleNamespace(books=books))
            filters = books.find.call_args.args[0]
            if search.strip():
                pattern = filters['$or'][0]['title']['$regex']
                self.assertIsNotNone(re.search(pattern, search.strip()))
                if search.strip() in ('[', '.*'):
                    self.assertIsNone(re.search(pattern, 'unrelated'))
            else:
                self.assertEqual(filters, {})
            self.assertEqual(response.headers['X-Has-Next'], 'true')
            books.find.return_value.skip.assert_called_with(5)
