import feedparser
import json
import re
import os
import sys
import time
import requests
from bs4 import BeautifulSoup
from loguru import logger
from art import *

# ロガーの設定
logger.remove()
logger.add(lambda msg: print(msg, end=""), colorize=True, format="<green>{time:YYYY-MM-DD at HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>")

# --- 取得元設定 ---
# arXiv は RSS(export.arxiv.org/rss/cs.AI) が間欠的に0件を返すため、Atom API に寄せる
# （ai_mail_digest の paper_sources.py と同じ取得手法。submittedDate 降順で週末でも空にならない）。
_ARXIV_API = 'http://export.arxiv.org/api/query'
_ARXIV_CATEGORIES = ('cs.AI', 'cs.LG', 'cs.CL')
_ARXIV_MAX_RESULTS = 50  # issue化は先頭30件のみ（issue_creator）なので数百件は不要
# HuggingFace は rsshub.app が恒常403のため、HF サイト自身が使う daily_papers エンドポイントへ。
_HF_API = 'https://huggingface.co/api/daily_papers'
_REQUEST_RETRIES = 3
_REQUEST_TIMEOUT = 30


class PaperScraper:
    def __init__(self, output_path='./papers.json'):
        self.output_path = output_path
        # API 取得用のシンプルなヘッダ（旧 self.headers の Accept-Encoding: br/zstd 等は
        # デコード不能で不安定になり得るため、UA のみに絞る）。
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        }

    # -------------------- 共通ユーティリティ --------------------
    def _request(self, url, retries=_REQUEST_RETRIES):
        """GET（リトライ/指数backoff付き）。成功時 response、失敗時 None。"""
        for attempt in range(retries):
            try:
                r = requests.get(url, headers=self.headers, timeout=_REQUEST_TIMEOUT)
                if r.status_code == 200:
                    return r
                logger.warning(f"HTTP {r.status_code}: {url}（{attempt + 1}/{retries}）")
            except Exception as e:
                logger.warning(f"リクエスト例外: {e}（{attempt + 1}/{retries}）")
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
        return None

    def extract_urls(self, text):
        github_pattern = r'https?://github\.com/\S+'
        huggingface_pattern = r'https?://huggingface\.co/\S+'
        github_urls = re.findall(github_pattern, text)
        huggingface_urls = re.findall(huggingface_pattern, text)
        return github_urls, huggingface_urls

    @staticmethod
    def _arxiv_id(s):
        """URL/ID 文字列から arXiv id（版番号なし・bare）を取り出す。無ければ None。"""
        m = re.search(r'(\d{4}\.\d{4,5})(v\d+)?', s or '')
        return m.group(1) if m else None

    def _arxiv_abs(self, s):
        aid = self._arxiv_id(s)
        return f"https://arxiv.org/abs/{aid}" if aid else None

    def _hf_link(self, pid):
        """HF paper.id が arXiv 形式なら arXiv abs URL、そうでなければ HF ペーパーページ。"""
        aid = self._arxiv_id(pid)
        return f"https://arxiv.org/abs/{aid}" if aid else f"https://huggingface.co/papers/{pid}"

    @staticmethod
    def _norm(text):
        return ' '.join((text or '').split())

    def _canon_key(self, paper):
        """dedup キー：arXiv id が取れれば `arxiv:<id>`（http/https・/abs/・vN 差異を吸収）、
        取れなければ link 完全一致（小文字）。※同一 run 内の papers.json 重複のみ防ぐ。
        既存 GitHub Issue との重複は issue_creator 側の別課題。"""
        aid = self._arxiv_id(paper.get('link', ''))
        if aid:
            return f"arxiv:{aid}"
        return f"link:{(paper.get('link') or '').strip().lower()}"

    # -------------------- arXiv（Atom API） --------------------
    def scrape_arxiv(self):
        """戻り値 (papers, fetch_failed)。fetch_failed=True は例外/非200（=真の障害）。"""
        logger.info("arXivからの論文スクレイピングを開始します（Atom API）")
        cats = '+OR+'.join(f'cat:{c}' for c in _ARXIV_CATEGORIES)
        url = (f"{_ARXIV_API}?search_query={cats}"
               f"&sortBy=submittedDate&sortOrder=descending&max_results={_ARXIV_MAX_RESULTS}")
        r = self._request(url)
        if r is None:
            logger.error("arXiv API の取得に失敗しました（fetch_failed）")
            return [], True

        soup = BeautifulSoup(r.content, 'lxml-xml')
        entries = soup.find_all('entry')
        logger.info(f"arXiv entries: {len(entries)}")

        papers = []
        for e in entries:
            try:
                title = self._norm(e.find('title').text if e.find('title') else 'タイトルなし')
                summary = self._norm(e.find('summary').text if e.find('summary') else '説明なし')
                id_text = e.find('id').text if e.find('id') else ''
                link = self._arxiv_abs(id_text) or (id_text or 'リンクなし')
                published = e.find('published').text if e.find('published') else '日付なし'
                authors = ", ".join(
                    a.find('name').text for a in e.find_all('author') if a.find('name')
                ) or '著者なし'
                github_urls, huggingface_urls = self.extract_urls(title + ' ' + summary)
                papers.append({
                    'title': title,
                    'summary': summary,
                    'link': link,
                    'published': published,
                    'authors': authors,
                    'github_urls': github_urls,
                    'huggingface_urls': huggingface_urls,
                    'source': 'arXiv',
                })
            except Exception as ex:
                logger.error(f"arXivエントリーの処理中にエラー: {ex}")
                continue

        logger.success(f"arXivから{len(papers)}件の論文を取得しました")
        return papers, False

    # -------------------- HuggingFace（公式 daily_papers API） --------------------
    def scrape_huggingface(self):
        """戻り値 (papers, fetch_failed)。"""
        logger.info("Hugging Faceからの論文スクレイピングを開始します（公式API）")
        r = self._request(_HF_API)
        if r is None:
            logger.error("Hugging Face API の取得に失敗しました（fetch_failed）")
            return [], True
        try:
            data = r.json()
        except Exception as ex:
            logger.error(f"Hugging Face API の JSON パースに失敗しました: {ex}（fetch_failed）")
            return [], True

        papers = []
        for item in (data or []):
            try:
                p = item.get('paper', {}) or {}
                title = self._norm(p.get('title') or item.get('title') or 'タイトルなし')
                summary = self._norm(p.get('summary') or item.get('summary') or '説明なし')
                pid = p.get('id') or ''
                link = self._hf_link(pid)
                published = item.get('publishedAt') or p.get('publishedAt') or '日付なし'
                authors_list = p.get('authors') or []
                authors = ", ".join(
                    a.get('name', '') for a in authors_list
                    if isinstance(a, dict) and a.get('name')
                ) or '著者なし'
                github_urls, huggingface_urls = self.extract_urls(title + ' ' + summary)
                # 現行踏襲: arXiv リンクなら source='arXiv'、それ以外は 'Hugging Face'（スペースあり）
                source = "arXiv" if "arxiv.org" in link else "Hugging Face"
                papers.append({
                    'title': title,
                    'summary': summary,
                    'link': link,
                    'published': published,
                    'authors': authors,
                    'github_urls': github_urls,
                    'huggingface_urls': huggingface_urls,
                    'source': source,
                })
            except Exception as ex:
                logger.error(f"Hugging Faceの論文処理中にエラー: {ex}")
                continue

        logger.success(f"Hugging Faceから{len(papers)}件の論文を取得しました")
        return papers, False

    # -------------------- 統合・保存・終了コード --------------------
    def scrape(self):
        tprint(">>  PaperScraper", font="rnd-large")
        logger.info("論文スクレイピングを開始します")
        arxiv_papers, arxiv_failed = self.scrape_arxiv()
        hf_papers, hf_failed = self.scrape_huggingface()

        # dedup（arXiv を先に置く → arXiv が薄い/0 の日は先頭30件に HF が入り Issue が復活）
        combined = []
        seen = set()
        for paper in arxiv_papers + hf_papers:
            key = self._canon_key(paper)
            if key in seen:
                continue
            seen.add(key)
            combined.append(paper)

        with open(self.output_path, 'w', encoding='utf-8') as f:
            json.dump(combined, f, ensure_ascii=False, indent=2)

        total = len(combined)
        logger.success(
            f"合計{total}件の論文を抽出しました"
            f"（arXiv {len(arxiv_papers)} / Hugging Face {len(hf_papers)} / dedup後 {total}）"
        )
        logger.info(f"結果を {self.output_path} に保存しました")

        # Fix C（結果ベース）: 障害は fail-loud、正当な空は warning
        if total > 0:
            if arxiv_failed:
                logger.warning("arXiv 取得に失敗しましたが、他ソースで成果ありのため成功終了します")
            if hf_failed:
                logger.warning("Hugging Face 取得に失敗しましたが、他ソースで成果ありのため成功終了します")
            return 0
        if arxiv_failed or hf_failed:
            logger.error("全ソース取得0件かつ障害（例外/非200）あり → 失敗終了 (exit 1)")
            return 1
        logger.warning("全ソース取得成功だが新着0件（正当な空）→ 成功終了 (exit 0)")
        return 0


if __name__ == '__main__':
    scraper = PaperScraper()
    exit_code = scraper.scrape()
    sys.exit(exit_code)
