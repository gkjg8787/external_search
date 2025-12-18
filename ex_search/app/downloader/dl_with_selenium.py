from urllib.parse import urlparse
import time
import json
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import structlog

from .constants import PAGE_LOAD_TIMEOUT, TAG_WAIT_TIMEOUT
from common.read_config import get_cookie_dir_path


class CookieManager:
    def __init__(self, filepath="selenium_cookies.json"):
        self.filepath = Path(filepath)
        self.logger = structlog.get_logger(self.__class__.__name__)

    def save_cookies(self, driver):
        if self.filepath.parent != Path("."):
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
        # 現在のブラウザセッションのCookieを取得
        cookies = driver.get_cookies()
        self.filepath.write_text(json.dumps(cookies, indent=2))
        self.logger.debug(f"Cookies saved to {self.filepath}")

    def load_cookies(self, driver):
        if not self.filepath.exists():
            self.logger.warning(f"Cookie file {self.filepath} does not exist.")
            return

        cookie_data = json.loads(self.filepath.read_text())

        for cookie in cookie_data:
            # Seleniumのadd_cookieは、現在開いているドメインと
            # Cookieのdomain属性が一致していないとエラーを出す場合があるため
            # 必要に応じて 'expiry' などの浮動小数点型を調整する
            if "expiry" in cookie:
                cookie["expiry"] = int(cookie["expiry"])
            driver.add_cookie(cookie)


def _set_cookies_on_selenium(driver, cookie_dict_list: list[dict]):
    if not cookie_dict_list:
        return
    for cookie_dict in cookie_dict_list:
        driver.add_cookie(cookie_dict)
    driver.refresh()


def download_with_selenium(
    url: str,
    driver,
    page_load_timeout: int,
    tag_wait_timeout: int,
    cookie_dict_list: list[dict] = [],
    wait_css_selector: str = "",
    page_wait_time: float = 0,
    cookie_save: bool = False,
    cookie_load: bool = False,
) -> str:
    driver.set_page_load_timeout(page_load_timeout)
    driver.get(url)

    if cookie_load or cookie_save:
        domain = urlparse(url).netloc
        cookie_manager = CookieManager(
            filepath=f"{get_cookie_dir_path()}/{domain}_selenium.json"
        )
        if cookie_load:
            cookie_manager.load_cookies(driver)
            driver.refresh()

    if cookie_dict_list:
        _set_cookies_on_selenium(driver=driver, cookie_dict_list=cookie_dict_list)

    if not wait_css_selector and page_wait_time > 0:
        time.sleep(page_wait_time)
    try:
        if wait_css_selector:
            target_element = WebDriverWait(driver, tag_wait_timeout).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, wait_css_selector))
            )
        html = driver.page_source
        if cookie_save:
            cookie_manager.save_cookies(driver)
    except TimeoutException as e:
        raise e
    except Exception as e:
        raise e
    finally:
        driver.quit()
    return html


def download_remotely(
    url: str,
    page_load_timeout: int = PAGE_LOAD_TIMEOUT,
    tag_wait_timeout: int = TAG_WAIT_TIMEOUT,
    selenium_url: str = "http://selenium:4444/wd/hub",
    cookie_dict_list: list[dict] = [],
    wait_css_selector: str = "",
    page_wait_time: float = 0,
    cookie_save: bool = False,
    cookie_load: bool = False,
):
    driver = webdriver.Remote(
        command_executor=selenium_url,
        options=webdriver.ChromeOptions(),
    )
    return download_with_selenium(
        url=url,
        driver=driver,
        page_load_timeout=page_load_timeout,
        tag_wait_timeout=tag_wait_timeout,
        cookie_dict_list=cookie_dict_list,
        wait_css_selector=wait_css_selector,
        page_wait_time=page_wait_time,
        cookie_save=cookie_save,
        cookie_load=cookie_load,
    )
