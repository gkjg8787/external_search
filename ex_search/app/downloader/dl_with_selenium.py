from urllib.parse import urlparse

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from .constants import PAGE_LOAD_TIMEOUT, TAG_WAIT_TIMEOUT


def _set_cookies_on_selenium(url: str, driver, cookie_dict_list: list[dict]):
    parsed_url = urlparse(url)
    base_url = parsed_url._replace(path="", params="", query="", fragment="").geturl()
    driver.get(base_url)
    for cookie_dict in cookie_dict_list:
        driver.add_cookie(cookie_dict)


def download_with_selenium(
    url: str,
    driver,
    page_load_timeout: int,
    tag_wait_timeout: int,
    cookie_dict_list: list[dict] = [],
    wait_css_selector: str = "",
) -> str:
    driver.set_page_load_timeout(page_load_timeout)
    if cookie_dict_list:
        _set_cookies_on_selenium(
            url=url, driver=driver, cookie_dict_list=cookie_dict_list
        )

    driver.get(url)
    css_selector = wait_css_selector
    try:
        if css_selector:
            target_element = WebDriverWait(driver, tag_wait_timeout).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, css_selector))
            )
        html = driver.page_source
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
    )
