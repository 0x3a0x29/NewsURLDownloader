import os
from Parsers import BaseParser,CNNParser
import json
from typing import Union, List
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver import ChromeOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class NewsURLDownloader:
    '''下载器类，用于批量下载网页并解析内容，多进程实现'''
    def __init__(self, urls:Union[str,List[str]], parserd_dir:str="parserd",ifDownload=True,user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")->None:
        if isinstance(urls, str):
            self.urls = [urls]
        else:
            self.urls = urls
        self.parserd_dir = parserd_dir
        self.ifDownload=ifDownload
        self.user_agent=user_agent
        
    @staticmethod
    def _create_driver(user_agent)->webdriver.Chrome: 
        chromedriver_path = r"driver\chromedriver.exe" #此处使用的是已经下载好的chromedriver.exe路径，需要更改为自己的路径
        service = Service(chromedriver_path) 
        options = ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--ignore-certificate-errors")  #忽略 SSL 错误
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-extensions")
        options.add_argument(f'--user-agent={user_agent}')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument('log-level=3')
        prefs = { #不加载图片，节省内存和加载时间
            "profile.managed_default_content_settings.images": 2
        }
        options.add_experimental_option("prefs", prefs)
        return webdriver.Chrome(service=service, options=options)
    def _batch_process_worker(self, urls: List[str], worker_id: int, parser: BaseParser = None) -> dict:
        '''每个进程中运行：初始化 driver，然后批量处理一个 url 子集'''
        driver = self._create_driver(self.user_agent)
        result = {}
        total = len(urls)
        for i, url in enumerate(urls):
            try:
                logging.info(f"[爬虫 {worker_id}] [{i+1}/{total}] 🔍 正在检查链接：{url}")
                driver.get(url)
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                final_url = driver.current_url
                # 🔐 先判断最终跳转 URL 是否允许被抓取
                if parser:
                    if not parser.url_allowed(final_url):
                        msg = f"禁止抓取（由 robots.txt 限制）：{final_url}"
                        logging.warning(f"[爬虫 {worker_id}] [{i+1}/{total}] ⛔ {msg}")
                        result[url] = {
                            'url': url,
                            'status': "illegal"
                        }
                        continue
                # ✅ 合法后再次访问以获取完整 HTML（可以跳过重复跳转，性能优化）
                logging.info(f"[爬虫 {worker_id}] [{i+1}/{total}] 🔽 抓取允许的页面：{final_url}")
                driver.get(final_url)
                WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                html = driver.page_source

                if parser:
                    parser.setURL(final_url)
                    parser.setHTML(html)
                    parsed = parser.parse()
                    result[url] = parsed
                    logging.info(f"[爬虫 {worker_id}] [{i+1}/{total}] 🧠 已完成解析：{final_url}")
                else:
                    result[url] = {"raw_html": html, "final_url": final_url}
                    logging.info(f"[爬虫 {worker_id}] [{i+1}/{total}] ✅ 已完成抓取：{final_url}")
            except Exception as e:
                logging.warning(f"[爬虫 {worker_id}] [{i+1}/{total}] ❌ 处理失败：{url} - {e}")
                result[url] = {"error": str(e)}
        driver.quit()
        logging.info(f"[爬虫 {worker_id}] 🛑 已退出")
        return result

    @staticmethod
    def _worker_run(urls: List[str], worker_id: int, parser: BaseParser = None) -> dict:
        '''独立进程中调用的入口点，等效于一个爬虫工作器'''
        downloader = NewsURLDownloader(urls)
        return downloader._batch_process_worker(urls, worker_id, parser)
    def download(self, parser: BaseParser = None, output_file: str = "output.json", max_workers: int = 4) -> None:
        '''将 URL 均衡地分配给多个子进程，使每个子进程任务尽可能平均，启动多个爬虫进程进行解析'''
        logging.info(f"🚀 使用 {max_workers} 个爬虫进程，准备分配 {len(self.urls)} 个 URL")

        total_urls = len(self.urls)
        base = total_urls // max_workers
        extra = total_urls % max_workers
        url_chunks = []
        start = 0
        for i in range(max_workers):
            end = start + base + (1 if i < extra else 0)
            url_chunks.append(self.urls[start:end])
            start = end
        results = {}
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(NewsURLDownloader._worker_run, chunk, i, parser)
                for i, chunk in enumerate(url_chunks) if chunk  # 防止空任务块
            ]
            for future in as_completed(futures):
                res = future.result()
                results.update(res)
        failed_urls = [url for url, content in results.items() if "error" in content]
        if failed_urls:
            logging.warning(f"⚠️ 总共有 {len(failed_urls)} 个 URL 解析失败。")
        else:
            logging.info(f"✅ 全部URL都解析成功。")
        output_path = os.path.join(self.parserd_dir, output_file)
        if self.ifDownload:
            os.makedirs(self.parserd_dir, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=4)
            logging.info(f"✅ 全部数据保存完成：{output_path}")
        else:
            logging.info(f"✅ 全部数据已解析完成，已经返回")
            return results

# 测试用例
if __name__ == "__main__":
    urls = ["https://edition.cnn.com/2022/01/31/uk/boris-johnson-sue-gray-report-gbr-intl/index.html",
            "https://edition.cnn.com/2025/04/06/us/trump-crackdown-university-protests-student-activism-hnk/index.html",
            "https://edition.cnn.com/2022/01/31/europe/analysis-downing-street-lockdown-parties-big-deal/index.html",
            "https://edition.cnn.com/2025/04/07/science/dire-wolf-de-extinction-cloning-colossal/index.html",
            "https://edition.cnn.com/2025/04/07/business/china-trump-tariffs-opportunity-analysis-intl-hnk/index.html",
            "https://edition.cnn.com/2025/04/03/business/trumps-reciprocal-tariffs-countries-list-dg/index.html",
            "https://edition.cnn.com/2025/04/07/politics/trump-bessent-tariff-message/index.html",
            "https://edition.cnn.com/europe/live-news/boris-johnson-party-report-latest-intl-gbr/index.html",
            "https://edition.cnn.com/2022/02/26/europe/ukraine-russia-invasion-refugee-border-crossing-wait-kyiv-lviv-intl/index.html",
            "https://edition.cnn.com/2022/02/26/sport/james-harden-philadelphia-76ers-debut-nba-spt-intl/index.html",
            "https://edition.cnn.com/2022/02/25/sport/champions-league-final-russia-ukraine-sport-reaction-spt-intl/index.html",
            "https://edition.cnn.com/2022/02/25/europe/kyiv-ukraine-russian-invasion-mood-friday-intl/index.html",
            "https://edition.cnn.com/europe/live-news/ukraine-russia-news-02-23-22/index.html",
            "https://edition.cnn.com/2022/02/23/europe/ukraine-government-commercial-organizations-data-wiping-hack/index.html",
            "https://edition.cnn.com/science/gallery/black-rhino-photos-c2e-spc/index.html",
            "https://edition.cnn.com/profiles/anderson-cooper-profile"
            ]
    downloader = NewsURLDownloader(urls)
    downloader.download(CNNParser())