from urllib.parse import urlparse
import asyncio

from pydantic import BaseModel, Field
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.gemini_api.models import HTMLConfigSearchResult, AskGeminiErrorInfo
from app.gemini_api.ask_gemini import (
    HTMLSelectorConfigGenerator,
    NoModelsAvailableError,
)
from app.gemini_api import web_scraper
from domain.schemas.search import search as search_schema
from domain.models.ai import ailog as m_ailog
from databases.sql.ai import repository as ai_repo


logger = structlog.get_logger(__name__)
CYCLE_WAIT_TIME = 1.5


class DefaultNodriverConfig(BaseModel):
    page_wait_time: int | None = Field(default=15, description="Wait time in seconds")


class DefaultDownloadConfig(BaseModel):
    nodriver: DefaultNodriverConfig = Field(default_factory=DefaultNodriverConfig)


class SearchPatternConfig(BaseModel):
    timeout: int | None = Field(
        default=None, description="Timeout for searching pattern in seconds"
    )
    optimize: bool = Field(
        default=True, description="Whether to optimize the search pattern"
    )
    default_config: DefaultDownloadConfig | None = Field(
        default=None, description="Default Download configuration"
    )


class DownloadConfigResult(BaseModel):
    htmlconfigsearchresult: HTMLConfigSearchResult
    download_config: search_schema.AskGeminiOptions
    download_preset: dict


async def _create_label_and_domain_from_url(url: str) -> dict:
    parsed_url = urlparse(url)
    domain = parsed_url.netloc.replace(".", "_")
    label = f"{domain}_auto_generated"
    return {"label": label, "domain": domain}


async def _generate_download_config_result(
    url: str,
    result: HTMLConfigSearchResult,
    preset: dict,
    nodriver_options: search_schema.NodriverOptions | None,
    httpx_options: search_schema.HttpxOptions | None,
) -> DownloadConfigResult:

    label_domain = await _create_label_and_domain_from_url(url)
    label = label_domain["label"]
    domain = label_domain["domain"]

    selector = result.item_selector or result.search_results_selector or ""
    if preset.get("nodriver") and nodriver_options:
        nodriver_options.wait_css_selector = search_schema.WaitCSSSelector(
            selector=selector,
            timeout=10,
            on_error=search_schema.OnError(
                action_type="retry", max_retries=2, wait_time=2.0
            ),
        )

    downloadconfigresult = DownloadConfigResult(
        htmlconfigsearchresult=result,
        download_config=search_schema.AskGeminiOptions(
            sitename=domain,
            label=label,
            nodriver=nodriver_options if preset.get("nodriver") else None,
            httpx=httpx_options if preset.get("httpx") else None,
        ),
        download_preset=preset,
    )
    if result.search_results_selector:
        downloadconfigresult.download_config.prompt = (
            search_schema.PromptOptions(
                add_prompt=f"#補足\n検索結果はCSSセレクタの{result.search_results_selector}で取得できます。"
            ),
        )
    return downloadconfigresult


async def get_download_config_pattern(
    url: str,
    search_word: str,
    search_pattern_config: SearchPatternConfig,
    db: AsyncSession,
) -> DownloadConfigResult | AskGeminiErrorInfo:
    workflow_config = {
        "basic_nodriver": {
            "nodriver": {
                "cookie": {"save": True, "load": False},
            },
            "ok": "end_success",
            "error": "cookie_nodriver",
            "need_optimize": "basic_httpx",
        },
        "cookie_nodriver": {
            "nodriver": {
                "cookie": {"save": True, "load": True},
            },
            "ok": "end_success",
            "error": "end_return",
            "need_optimize": "cookie_httpx",
        },
        "basic_httpx": {
            "httpx": {
                "cookie": {"save": True, "load": False},
            },
            "ok": "end_success",
            "error": "cookie_httpx",
            "need_optimize": "end_success",
        },
        "cookie_httpx": {
            "httpx": {
                "cookie": {"save": True, "load": True},
            },
            "ok": "end_success",
            "error": "end_return",
            "need_optimize": "end_success",
        },
    }

    label_domain = await _create_label_and_domain_from_url(url)
    label = label_domain["label"]
    last_execute_result = {}

    async def _save_log(response: dict, error_info: dict | None, meta_output: dict):
        log_entry = m_ailog.DownloadConfigGenerationLog(
            label=label,
            target_url=url,
            search_keyword=search_word,
            response=response,
            error_info=error_info,
            meta={
                "input": {"search_pattern_config": search_pattern_config.model_dump()},
                "output": meta_output,
            },
        )
        repo = ai_repo.DownloadConfigGenerationLogRepository(db)
        await repo.save(log_entry)

    optimized_result = None
    current_preset = "basic_nodriver"
    preset_route = []
    while current_preset not in ["end_success", "end_return"]:
        preset = workflow_config[current_preset]
        preset_route.append(current_preset)
        nodriver_options = None
        httpx_options = None
        if (
            search_pattern_config.default_config
            and search_pattern_config.default_config.nodriver
            and search_pattern_config.default_config.nodriver.page_wait_time
        ):
            page_wait_time = (
                search_pattern_config.default_config.nodriver.page_wait_time
            )
        else:
            page_wait_time = 15

        if search_pattern_config.timeout:
            timeout = search_pattern_config.timeout
        else:
            timeout = 30
        if preset.get("nodriver") is not None:
            logger.debug("trying download config with nodriver preset", preset=preset)
            nodriver_options = search_schema.NodriverOptions(
                cookie=search_schema.Cookie(
                    save=preset["nodriver"]["cookie"]["save"],
                    load=preset["nodriver"]["cookie"]["load"],
                ),
                page_wait_time=page_wait_time,
            )
            ok, result = await web_scraper.get_html_with_nodriver_api(
                command=web_scraper.GetCommandWithNodriver(
                    url=url,
                    nodriver_options=nodriver_options,
                    timeout=timeout,
                )
            )
            if not ok or isinstance(result, str):
                err = AskGeminiErrorInfo(error=result, error_type="DownloadError")
                await _save_log({}, err.model_dump(), {})
                current_preset = preset["error"]
                continue
            html_str = result.result
        elif preset.get("httpx") is not None:
            logger.debug("trying download config with httpx preset", preset=preset)
            httpx_options = search_schema.HttpxOptions(
                cookie=search_schema.Cookie(
                    save=preset["httpx"]["cookie"]["save"],
                    load=preset["httpx"]["cookie"]["load"],
                )
            )
            ok, html_str = await web_scraper.get_html(
                command=web_scraper.GetCommandWithHttpx(
                    url=url,
                    httpx_options=httpx_options,
                    timeout=timeout,
                )
            )
            if not ok or not html_str:
                err = AskGeminiErrorInfo(error=html_str, error_type="DownloadError")
                await _save_log({}, err.model_dump(), {})
                current_preset = preset["error"]
                continue
        else:
            logger.error("invalid preset configuration")
            return AskGeminiErrorInfo(
                error="invalid preset configuration", error_type="ConfigError"
            )

        logger.info(
            "download successful. generating html selector config",
            url=url,
            search_word=search_word,
        )
        generator = HTMLSelectorConfigGenerator(
            html_str=html_str,
            search_word=search_word,
        )
        result = await generator.execute()
        if hasattr(result, "model_dump"):
            last_execute_result = result.model_dump()
        else:
            last_execute_result = {}
        if (
            isinstance(result, HTMLConfigSearchResult)
            and result.search_results_displayed == "displayed"
            and result.search_results_selector
        ):

            optimized_result = await _generate_download_config_result(
                url=url,
                result=result,
                preset=preset,
                nodriver_options=nodriver_options,
                httpx_options=httpx_options,
            )
            if not search_pattern_config.optimize:
                logger.info(
                    "generated html selector config without optimization",
                    preset=preset,
                    download_config=optimized_result.model_dump(exclude_unset=True),
                )
                await _save_log(
                    last_execute_result,
                    None,
                    {
                        "preset": preset,
                        "optimized_result": optimized_result.model_dump(
                            exclude_unset=True
                        ),
                    },
                )
                return optimized_result
            current_preset = preset["need_optimize"]
            logger.debug("optimized html selector config generated", preset=preset)
            await asyncio.sleep(CYCLE_WAIT_TIME)
            continue
        if isinstance(result, AskGeminiErrorInfo):
            if result.error_type == NoModelsAvailableError.__name__:
                logger.error(
                    "no models available for html selector config generation",
                    preset=preset,
                )
                await _save_log(last_execute_result, result.model_dump(), {})
                return result
            logger.info(
                "failed to generate html selector config",
                preset=preset,
                error_type=result.error_type,
                error_msg=result.error,
            )
            current_preset = preset["error"]
            await asyncio.sleep(CYCLE_WAIT_TIME)
            continue
        elif isinstance(result, HTMLConfigSearchResult):
            logger.info(
                "generated html selector config but no search results found",
                preset=preset,
                last_execute_result=last_execute_result,
            )
            current_preset = preset["error"]
            await asyncio.sleep(CYCLE_WAIT_TIME)
            continue
        else:
            logger.error(
                "unexpected result type from HTMLSelectorConfigGenerator",
                result_type=type(result).__name__,
            )
            err = AskGeminiErrorInfo(
                error_msg="unexpected error during html selector config generation"
            )
            await _save_log(last_execute_result, err.model_dump(), {})
            if optimized_result:
                logger.warning(
                    "unexpected error during html selector config generation, but continuing as optimized_result exists"
                )
                current_preset = preset["need_optimize"]
                continue
            return err
    if optimized_result is None:
        logger.warning("failed to generate any download config preset worked")
        err = AskGeminiErrorInfo(
            error="all download config presets failed to generate valid html selector config",
            error_type="NoValidConfig",
        )
        await _save_log(last_execute_result, err.model_dump(), {})
        return err
    logger.info(
        "all download config presets tried",
        preset_route=preset_route,
        optimized_result=optimized_result.model_dump(),
    )
    await _save_log(
        last_execute_result,
        None,
        {
            "preset": preset,
            "optimized_result": optimized_result.model_dump(exclude_unset=True),
        },
    )
    return optimized_result
