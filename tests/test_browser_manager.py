import unittest

from src.services.browser.browser_manager import BrowserManager


class LoginStateTests(unittest.IsolatedAsyncioTestCase):
    async def test_login_is_required_when_login_button_is_visible(self):
        manager = BrowserManager()

        class Locator:
            async def is_visible(self):
                return True

        class Page:
            def locator(self, selector):
                self.selector = selector
                return Locator()

        page = Page()
        previous_page = manager.page
        manager.page = page
        try:
            self.assertTrue(await manager._needs_login())
            self.assertEqual(page.selector, "button.agent-dialogue__tool__login")
        finally:
            manager.page = previous_page

    async def test_login_is_not_required_when_login_button_is_hidden(self):
        manager = BrowserManager()

        class Locator:
            async def is_visible(self):
                return False

        class Page:
            def locator(self, selector):
                return Locator()

        previous_page = manager.page
        manager.page = Page()
        try:
            self.assertFalse(await manager._needs_login())
        finally:
            manager.page = previous_page


if __name__ == "__main__":
    unittest.main()
