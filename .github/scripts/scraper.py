import feedparser
import json
import re
import os
import requests
from bs4 import BeautifulSoup
from loguru import logger
from art import *

# ロガーの設定
logger.remove()
logger.add(lambda msg: print(msg, end=""), colorize=True, format="<green>{time:YYYY-MM-DD at HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>")

class PaperScraper:
    def __init__(self, output_path='./papers.json'):
        self.output_path = output_path
        # self.headers = {
        #     'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        # }
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'Referer': 'https://www.google.com/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
            'Cache-Control': 'max-age=0',
            'Cookie': (
                'cb_analytics_consent=granted; cid=Cih3B2aG4+lnRAAbkp93Ag==; featureFlagOverride=%7B%7D; pxcts=b38e7a48-3a2f-11ef-8c91-ae3959311937; '
                '_pxvid=b38e6783-3a2f-11ef-8c90-fbdf448e80ae; _gcl_au=1.1.361638907.1720116203; _fbp=fb.1.1720116203493.342101767961239072; '
                'drift_aid=db351671-91e5-4a74-9ea7-0d44c6c9c110; driftt_aid=db351671-91e5-4a74-9ea7-0d44c6c9c110; drift_eid=7a369f22-3b56-48b8-9cc4-1f9ba871b792; '
                '_delighted_web={%220SrRdbRV9pdk0Aem%22:{%22_delighted_fst%22:{%22t%22:%221720127651486%22}%2C%22_delighted_lst%22:{%22t%22:%221717382555000%22%2C%22m%22:{%22token%22:%22ubPU8vJjUNq7feXB4TSjhkim%22}}}}; '
                '_gid=GA1.2.2065042704.1721009702; _pxhd=cwuYdfcnPgguWE1djIp27dcoEW7ZGGXD/VhJpUy/WCw2y/-0dzuJVPB4IqUdZ0lm3hTzAXmkKCWR32t68D1EVw; '
                '_mkto_trk=id:976-JJA-800&token:_mch-crunchbase.com-1721012954157-40861; _hp2_id.973801186=%7B%22userId%22%3A%227178004799793612%22%2C%22pageviewId%22%3A%222723027781072096%22%2C%22sessionId%22%3A%223748226255128517%22%2C%22identity%22%3Anull%2C%22trackerVersion%22%3A%224.0%22%7D; '
                '__cflb=02DiuJLCopmWEhtqNz3x2VesGhPn4wGcKc64wQqQJE53A; xsrf_token=WqqF1DEz3noifXA4nmmVP4k8tJpLdzzRH6zh5fFYFJU=; '
                'OptanonConsent=isGpcEnabled=0&datestamp=Tue+Jul+16+2024+23%3A41%3A58+GMT%2B0900+(%E6%97%A5%E6%9C%AC%E6%A8%99%E6%BA%96%E6%99%82)&version=202304.1.0&browserGpcFlag=0&isIABGlobal=false&hosts=&landingPath=NotLandingPage&groups=C0001%3A1%2CC0002%3A1%2CC0003%3A1%2CC0004%3A1&AwaitingReconsent=false; '
                '_ga=GA1.2.1976840591.1720116203; _uetsid=0a420620425011ef8ddd27c59b7d8186; _uetvid=b4e2e730e00f11ee919f4741304a2f9a; '
                '_px3=f3da54cd8c63774b540d6d1a536af869de7910a2e7a8113c145151f7831c1747:iiB5roSyj9lzsKMbeZpoMZbkIuHQfKQyu9/dTEhkLTVR3FiSIIa0jzG4FP9uJMHvHNp1HZTSp5FkL3dpEYynAw==:1000:ObRFmPUiI9U+ss/bRb+G8ghzMEObP1Ns3yh/kvo9m33hHdZxFLyfVR2XNoQhL/tASbDp8Gx9Mub/wpFZwwP+wgh6znGzmVR2apxhqYIsYuYz4wT6TV+ESybDWu8BLLpEwDHuRS7d2Eew6DuGXA02QS/MyEmw2FseFRAu+ZKGOLwNhHcs1M6c1UpTu04vkiUFQNn5z/7XJXRgso5dkYGNYAkWPgZv05b3fS/kon7R5FA=; _ga_PGHC4BDGLM=GS1.1.1721140815.16.1.1721142141.0.0.0; _ga_97DKWJJNRK=GS1.1.1721140815.16.1.1721142141.60.0.0; '
                'fs_uid=#BA8KZ#a04d025e-a91d-4177-8f55-cc027d3e43a3:47fae02e-d687-4bf4-98b1-39fc0bad455c:1721140816730::3#3b0ce6bf#/1746363963; __cf_bm=Q87M6pr62hOit0kwXXFeHRthzIsGTMPT4Seslcdt9eA-1721142484-1.0.1.1-cc_eAjlepAHHNhgt0QbCR7KkCpAibTE65cjbN5qEiXavPW9Sh5qOz0JBkuDKhvGaC200yXIEcZQqHHf0mcoqqA; '
                'authcookie=eyJhbGciOiJIUzUxMiJ9.eyJqdGkiOiI5ZDI0MzY2ZS1hMDdkLTQxNWMtOWJhMC01NjRjNGNlY2VmMzAiLCJpc3MiOiJ1c2Vyc2VydmljZV85YWZkNWYwY183MzciLCJzdWIiOiI3YTM2OWYyMi0zYjU2LTQ4YjgtOWNjNC0xZjliYTg3MWI3OTIiLCJleHAiOjE3MjExNDMwODQsImlhdCI6MTcyMTE0Mjc4NCwicHJpdmF0ZSI6IlhBbVRTc2V5enVsWjVuRE5BTnlJOTBoQUxkVVRpSUJwSzBlTUFkTWNrdlhsZFVIN29GWDZPY3dDRi8rR0cvVTVHSS9ZT24zeEtzQ29hTkU2WlJ1Uys1bC9YT3BlKzNQTUlzTUJ4bVZTRHRWNHBwR1cvTHdoQ0RiWkpEYis1UWpwZjNsY2ZxT3Z3bmhIcEp1RGx6eFZTb09Dblh5MHovekFHUXZnNjNlMjJZL0FiYjBMMkVnL2xpc2JZOVR3bnlBZ3NnN1IvYkRQRlRNT0tud3RmU1lIVjQwZCtBUFhNZlZVOVpOOGdUaHJNSDR4cjBtMkZmcTNHK0ZIMmpaUEhDWEdJb09PRHZidUNUbTBIUmdDazc0QzB6M0tYcFJVWW95Mkg0NkhBYWFqSGk2RjliRkhUdUN2cy9NQm5zSEgyVFcxZGJ4cm5DdUlraGlMZzQrV2VVUjdua0hKSUgyTE1kUnVnWEEvZ1Z6d0hYQ0F3U3BGVHNjaVZKb24yZEZtV3FOWDhoR1RkbTY3eXdkZmRGVmQwSXFRdHhaM3gxQUhBdmE2YjRQbmdYMzhjSmxZQVJDMUZSSXBqQUlTWk1rMWV4VC83Ly9xL25nRzNneVM5STBVYm5TWFVCVGdPS01VU0lCU2ZRbG9scmZ2bXRsOWZNb2p5eUxPWTc4Uko3L0lOdjl3cEFUTkFHQTBEK2cxak1yRHpCVXBGNHZVelIrSUhzYVdqSDNnTC9kNklHUVdzSFB6Q2tjSklNcDQwTzFxTy9qUFlSTjk3VERlWElTOWZtb3lYMkdOQnNGSEJCZnN3OFoweFZUek5EcXM0RlJvdE5wWnAxZDMvSmVNeTVsMUUwUlZvbXRZdHN1aUVnRCs4dTR0M0ZEcmNET2hiT2pWeEdycDRZalMvSDJHWE83UVVCdjJ3clZNMk9vcVNOOW5MWXdYQWJEVTBoRFlLcUxIcWxCQVlrcVRlTDFDTlNDMWdOdkpHVldHV0puK3kxQW5ZTEd5OFZQaFM5YmlYb3BXWElWdlFIZjNkL2VlTjRZWmJtRXpoQmZBRms1WW9sK1RtcTQ1NDVMQXZXblVoZXVXNHJDdmNxemphY0Q1ZVlialdVZHFMVHJyZzVXVUg2b2EyQXVJdzRJU0V5amlqenNGTkhEQWs0S2phcEFkSUtnVGJzOFpPMlZoU2swSk1Yay81SzlaUVdJa0FCcW1EaEROZEttVks3RnY3eno4RGQ0dE9UeUhPVDFvWUtaTmdSMmNJQ1ZNRTdVc3RDcnF4MlEzbURzN2krcmpGZjFoaS96WEpReGJUWGhxMFFscGM0V2JYZUdWWHRpQ0VvSVl0R0VEb1RtTzg5U0prL0RVKythaU5QdEd3YTF2Tm5aVzhHVjBDcGh4dmM5WENuMUZKZGlhSDBSRFpvRUtGNFVHWVJZQkN2ZTUxOVZaMkRDdjAreWRUUmdUc0lDR2RialRkU0JkM0RFYlV1TXVNRHliTnhWSlFGTEZkV1ZHdlE4OER4Qm1LWmR1T1lpRVVJV09oaDE3bTZ6VSIsInB1YmxpYyI6eyJzZXNzaW9uX2hhc2giOiItMTQ5Njc4NjMzNCJ9fQ.XVd1U4JlVhTGoJnvLVc9rMnlLpC2OQmSMb8itn6Gt68bTEQLUAKbThlZIcD0C02gJfOqjCJv1g36Py18pjfeWQ=='
            ),
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"macOS"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1'
        }

    def extract_urls(self, text):
        github_pattern = r'https?://github\.com/\S+'
        huggingface_pattern = r'https?://huggingface\.co/\S+'

        github_urls = re.findall(github_pattern, text)
        huggingface_urls = re.findall(huggingface_pattern, text)

        return github_urls, huggingface_urls

    def scrape_arxiv(self):
        logger.info("arXivからの論文スクレイピングを開始します")
        url = 'http://export.arxiv.org/rss/cs.CV'
        feed = feedparser.parse(url)

        papers = []
        for entry in feed.entries:
            try:
                full_text = entry.title + ' ' + entry.summary
                github_urls, huggingface_urls = self.extract_urls(full_text)
                if github_urls or huggingface_urls:
                    paper = {
                        'title': entry.title,
                        'summary': entry.summary,
                        'link': entry.link,
                        'published': getattr(entry, 'published', 'No date available'),  # デフォルト値を設定
                        'github_urls': github_urls,
                        'huggingface_urls': huggingface_urls,
                        'source': 'arXiv'
                    }
                    papers.append(paper)
                    logger.debug(f"論文を追加しました: {entry.title}")
    
                if len(papers) >= 30:
                    break
            except AttributeError as e:
                logger.error(f"arXivエントリーの処理中にエラーが発生しました: {str(e)}")
                continue

        logger.success(f"arXivから{len(papers)}件の論文を取得しました")
        return papers

    def scrape_huggingface(self):
        logger.info("Hugging Faceからの論文スクレイピングを開始します")
        url = 'http://rsshub.app/huggingface/daily-papers'
        
        # RSSフィードのリクエストを実行
        response = requests.get(url, headers=self.headers)
        logger.debug(f"ステータスコード: {response.status_code}")  # ステータスコードをデバッグ出力
        
        # BeautifulSoupでRSSフィードを解析
        soup = BeautifulSoup(response.content, 'lxml-xml')
        logger.debug(f"RSSフィードの内容: {soup.prettify()}")  # フィード内容をデバッグ出力
        
        # <item>タグを取得
        items = soup.find_all('item')
        logger.info(f"見つかったアイテム数: {len(items)}")

        papers = []
        for item in items:
            try:
                title = item.find('title').text if item.find('title') else 'タイトルなし'
                description = item.find('description').text if item.find('description') else '説明なし'
                link = item.find('link').text if item.find('link') else 'リンクなし'
                published = item.find('pubDate').text if item.find('pubDate') else '日付なし'
                authors = item.find('author').text if item.find('author') else '著者なし'

                full_text = title + ' ' + description
                github_urls, huggingface_urls = self.extract_urls(full_text)
                paper = {
                    'title': title,
                    'summary': description,
                    'link': link,
                    'published': published,
                    'authors': authors,
                    'github_urls': github_urls,
                    'huggingface_urls': huggingface_urls,
                    'source': 'Hugging Face'
                }
                papers.append(paper)
                logger.debug(f"論文を追加しました: {title}")

            except Exception as e:
                logger.error(f"Hugging Faceの論文取得中にエラーが発生しました: {str(e)}")
                continue

        logger.success(f"Hugging Faceから{len(papers)}件の論文を取得しました")
        return papers

    def scrape(self):
        tprint(">>  PaperScraper", font="rnd-large")
        logger.info("論文スクレイピングを開始します")
        arxiv_papers = self.scrape_arxiv()
        huggingface_papers = self.scrape_huggingface()

        all_papers = arxiv_papers + huggingface_papers

        with open(self.output_path, 'w', encoding='utf-8') as f:
            json.dump(all_papers, f, ensure_ascii=False, indent=2)

        logger.success(f"合計{len(all_papers)}件の論文を抽出しました")
        logger.info(f"arXiv: {len(arxiv_papers)}件")
        logger.info(f"Hugging Face: {len(huggingface_papers)}件")
        logger.info(f"結果を {self.output_path} に保存しました")

if __name__ == '__main__':
    scraper = PaperScraper()
    scraper.scrape()
