"""浏览器管理器模块"""

import asyncio
import logging
from typing import Dict, List, Optional
from urllib.parse import urlparse

from playwright.async_api import Browser, Page, async_playwright

from src.config import settings
from src.utils.qr_utils import print_qr_to_terminal

logger = logging.getLogger(__name__)


class BrowserManager:
    """浏览器管理器 - 单例模式"""

    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "initialized"):
            self.browser: Optional[Browser] = None
            self.page: Optional[Page] = None
            self.playwright = None
            self._route_handler = None
            self._is_logged_in = False
            self._initialized = True

    async def ensure_browser(self):
        """确保浏览器已初始化"""
        async with self._lock:
            if self.browser is None or self.page is None:
                await self._init_browser()

    async def _init_browser(self):
        """初始化浏览器"""
        if self.playwright is None:
            self.playwright = await async_playwright().start()

        if self.browser is None:
            self.browser = await self.playwright.chromium.launch(headless=True)

        if self.page is None:
            self.page = await self.browser.new_page()
            await self._load_page()

    async def _load_page(self):
        """预加载页面"""
        logger.info("[Browser] 预加载 Yuanbao 页面...")
        try:
            await self.page.goto(settings.page_url, timeout=settings.page_timeout)
            await self.page.wait_for_timeout(3000)
            logger.info("[Browser] 页面加载完成")
        except Exception as e:
            logger.error(f"[Browser] 页面加载失败: {e}")
            raise

    @staticmethod
    def _parse_cookie_string(cookie_str: str) -> List[Dict]:
        """将 Cookie 字符串解析为 Playwright Cookie 列表

        Args:
            cookie_str: 形如 `hy_user=xxx; hy_token=yyy` 的 Cookie 字符串

        Returns:
            List[Dict]: Playwright add_cookies 所需格式
        """
        parsed = urlparse(settings.page_url)
        domain = parsed.hostname or "yuanbao.tencent.com"

        cookies: List[Dict] = []
        for part in cookie_str.split(";"):
            part = part.strip()
            if not part or "=" not in part:
                continue
            name, value = part.split("=", 1)
            name, value = name.strip(), value.strip()
            if not name:
                continue
            cookies.append(
                {
                    "name": name,
                    "value": value,
                    "domain": domain,
                    "path": "/",
                }
            )
        return cookies

    async def _needs_login(self) -> bool:
        """检测当前页面是否仍需要登录"""
        try:
            login_button = self.page.get_by_role("img").first
            await login_button.wait_for(state="visible", timeout=5000)
            return True
        except Exception:
            return False

    async def _login_with_cookies(self) -> Dict:
        """使用配置的 Cookie 登录

        Returns:
            Dict: 登录结果字典
        """
        cookie_list = self._parse_cookie_string(settings.cookies)
        if not cookie_list:
            return {"success": False, "message": "Cookie 格式无效"}

        names = [c["name"] for c in cookie_list]
        logger.info(f"[Browser] 检测到 Cookie 配置，优先使用 Cookie 登录: {names}")

        try:
            await self.page.context.add_cookies(cookie_list)
            await self.page.reload(timeout=settings.page_timeout)
            await self.page.wait_for_timeout(3000)

            if await self._needs_login():
                logger.warning("[Browser] Cookie 登录失败，页面仍需登录")
                return {"success": False, "message": "Cookie 无效或已过期"}

            self._is_logged_in = True
            logger.info("[Browser] Cookie 登录成功")
            return {"success": True, "message": "Cookie 登录成功"}
        except Exception as e:
            logger.error(f"[Browser] Cookie 登录失败: {e}")
            return {"success": False, "message": f"Cookie 登录失败: {str(e)}"}

    async def _login_with_qrcode(self) -> Dict:
        """扫码登录

        Returns:
            Dict: 登录结果字典
        """
        try:
            login_button = self.page.get_by_role("img").first
            await login_button.wait_for(state="visible")
            await login_button.click()

            iframe_frame = self.page.frame_locator("iframe")
            qrcode_locator = iframe_frame.get_by_role("img")
            await qrcode_locator.wait_for(state="visible", timeout=10000)

            await qrcode_locator.screenshot(path=settings.qrcode_path)
            logger.info(f"[Browser] 二维码已保存至 {settings.qrcode_path}")

            print_qr_to_terminal(settings.qrcode_path)

            logger.info("[Browser] 等待扫码完成...")
            try:
                await login_button.wait_for(state="detached", timeout=settings.login_timeout)
                logger.info("[Browser] 扫码成功，按钮已消失")
                self._is_logged_in = True
                return {
                    "success": True,
                    "message": "登录成功",
                    "qrcode_path": settings.qrcode_path,
                }
            except TimeoutError:
                logger.warning("[Browser] 扫码超时或未检测到登录成功")
                return {
                    "success": False,
                    "message": "扫码超时",
                    "qrcode_path": settings.qrcode_path,
                }
        except Exception as e:
            logger.error(f"[Browser] 扫码登录失败: {e}")
            return {
                "success": False,
                "message": f"扫码登录失败: {str(e)}",
            }

    async def login(self) -> Dict:
        """执行登录流程：优先 Cookie，未配置或失败时回退扫码

        Returns:
            Dict: 登录结果字典
        """
        await self.ensure_browser()

        if settings.cookies.strip():
            result = await self._login_with_cookies()
            if result.get("success"):
                return result
            logger.warning(f"[Browser] Cookie 登录未成功（{result.get('message')}），回退到扫码登录")
        else:
            logger.info("[Browser] 未配置 Cookie，使用扫码登录")

        return await self._login_with_qrcode()

    async def get_headers(self) -> Optional[Dict]:
        """获取请求头

        Returns:
            Optional[Dict]: 请求头字典，失败返回 None
        """
        await self.ensure_browser()
        captured_headers = {}

        async def handle_route(route, request):
            nonlocal captured_headers
            url = request.url
            headers = request.headers

            if settings.header_api_pattern in url:
                if "x-uskey" in headers and not captured_headers.get("x-uskey"):
                    captured_headers = headers
                    logger.info(f"[Browser] 捕获到请求头 from {url}")

            await route.continue_()

        if self._route_handler:
            try:
                self.page.remove_route("**/*")
            except Exception:
                pass

        await self.page.route("**/*", handle_route)
        self._route_handler = handle_route

        try:
            reload_task = asyncio.create_task(self.page.reload(timeout=10000))

            start_time = asyncio.get_event_loop().time()

            while (asyncio.get_event_loop().time() - start_time) < settings.header_timeout:
                if captured_headers.get("x-uskey"):
                    break
                await asyncio.sleep(0.05)

            if captured_headers.get("x-uskey"):
                reload_task.cancel()
                try:
                    await reload_task
                except asyncio.CancelledError:
                    pass

        except Exception as e:
            logger.error(f"[Browser] 获取请求头失败: {e}")
        finally:
            if self._route_handler:
                try:
                    self.page.remove_route("**/*")
                    self._route_handler = None
                except Exception:
                    pass

        return captured_headers if captured_headers.get("x-uskey") else None

    async def get_cookies(self) -> Dict[str, str]:
        """获取 Cookie

        Returns:
            Dict[str, str]: Cookie 字典
        """
        await self.ensure_browser()

        if not self.page:
            return {}

        cookies = await self.page.context.cookies()
        return {c["name"]: c["value"] for c in cookies}

    async def close(self):
        """关闭浏览器"""
        async with self._lock:
            tasks = []
            if self.page:
                tasks.append(self.page.close())
                self.page = None
            if self.browser:
                tasks.append(self.browser.close())
                self.browser = None
            if self.playwright:
                tasks.append(self.playwright.stop())
                self.playwright = None
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)


# 全局单例
browser_manager = BrowserManager()
