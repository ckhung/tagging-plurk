#!/usr/bin/env python3
import argparse, html, json, re, sys
from html.parser import HTMLParser
from typing import List, Tuple
from urllib.parse import urljoin


class PlurkHTMLParser(HTMLParser):
    '''自訂 HTML 解析器，用以剝離標籤並提取 <a> 的 href 及 <img> 的 src'''

    def __init__(self, base_url: str = 'https://www.plurk.com/'):
        super().__init__()
        self.base_url = base_url
        self.text_parts: List[str] = []
        self.urls: List[str] = []
        self.imgs: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, str]]):
        attr_dict = dict(attrs)

        if tag == 'a':
            href = attr_dict.get('href')
            if not href: return
            full_url = urljoin(self.base_url, href)
            # 簡單過濾 javascript: 或 anchor 連結
            if full_url.startswith(('http://', 'https://')):
                self.urls.append(full_url)
        elif tag == 'img':
            src = attr_dict.get('src')
            if not src: return
            full_url = urljoin(self.base_url, src)
            if full_url.startswith(('http://', 'https://')):
                self.imgs.append(full_url)

    def handle_data(self, data: str):
        if data:
            self.text_parts.append(data)

    def get_clean_text(self) -> str:
        # 合併純文字，清理多餘空白與換行
        raw_text = ''.join(self.text_parts)
        # 解碼 HTML entities (如 &amp; &lt;)
        decoded_text = html.unescape(raw_text)
        # 整理連續的空白與換行
        cleaned_text = re.sub(r'\s+', ' ', decoded_text).strip()
        return cleaned_text


def process_html(
    html_content: str, base_url: str
) -> Tuple[str, List[str], List[str]]:
    parser = PlurkHTMLParser(base_url=base_url)
    parser.feed(html_content)

    # 去重複但維持原始出現順序
    seen_urls = set()
    unique_urls = [
        u for u in parser.urls if not (u in seen_urls or seen_urls.add(u))
    ]

    seen_imgs = set()
    unique_imgs = [
        i for i in parser.imgs if not (i in seen_imgs or seen_imgs.add(i))
    ]

    return parser.get_clean_text(), unique_urls, unique_imgs


def main():
    parser = argparse.ArgumentParser(
        description='讀取 stdin 的 JSONL，解析指定的 HTML 欄位，並將結果寫入新的欄位，輸出至 stdout。',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-r', '--raw-text', required=True,
        help='來源 HTML 內容所在的 JSON key (例如: "content")' )
    parser.add_argument('-t', '--out-text', required=True,
        help='儲存去除 HTML 標籤後純文字的 JSON key (例如: "plain_text")' )
    parser.add_argument('-u', '--out-urls', required=True,
        help='儲存提取出的超連結陣列的 JSON key (例如: "urls")' )
    parser.add_argument('-i', '--out-imgs', required=True,
        help='儲存提取出的圖片網址陣列的 JSON key (例如: "imgs")' )
    parser.add_argument('--base-url', default='https://www.plurk.com/',
        help='相對路徑補全用的 Base URL' )

    args = parser.parse_args()

    # 讀取 stdin，逐行處理 JSONL
    for line_num, line in enumerate(sys.stdin, 1):
        line = line.strip()
        if not line:
            continue

        try:
            record = json.loads(line)
        except json.JSONDecodeError as e:
            sys.stderr.write(
                f'[Warning] Skipping invalid JSON at line {line_num}: {e}\n'
            )
            continue

        # 取得 HTML 欄位內容，若不存在則給予空字串
        html_content = record.get(args.raw_text, '')

        if html_content:
            clean_text, urls, imgs = process_html(html_content, args.base_url)
        else:
            clean_text, urls, imgs = '', [], []

        # 寫入指定的輸出欄位
        record[args.out_text] = clean_text
        record[args.out_urls] = urls
        record[args.out_imgs] = imgs

        # 輸出處理完畢的 JSON 到 stdout
        sys.stdout.write(json.dumps(record, ensure_ascii=False) + '\n')


if __name__ == '__main__':
    main()
