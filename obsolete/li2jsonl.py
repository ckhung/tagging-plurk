#!/usr/bin/env python3
import sys
import re
import json

def strip_html(text):
    """移除內容中大部分的 HTML tags， 僅保留 <img /> 與純文字以供 LLM 處理。"""
    return re.sub(r'<(?!img\b)[^>]+>', ' ', text, flags=re.I).strip()

def process_plurks(files):
    # Regex 說明：
    # 1. 抓取 href 內的 URL
    # 2. 抓取 <a> 標籤內的日期時間
    # 3. 抓取使用者 ID
    # 4. 抓取 qualifier span 內的動作 (分享/轉噗/喜歡)
    # 5. 抓取剩下的所有內容作為 raw_content
    pattern = re.compile(
        r"^<li><a href='(?P<url>[^']+)'>(?P<ts>[^<]+)</a>\s+(?P<user>\w+\s+)?"
        r"<span class='qualifier[^']*'>(?P<action>[^<]+)</span>\s*(?P<content>.*)$"
    )
    for filepath in files:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line.startswith('<li>'):
                        continue
                    
                    match = pattern.match(line)
                    if match:
                        data = match.groupdict()
                        # 清理 HTML 內容以便後續進行 Semantic Analysis
                        data['text_only'] = strip_html(data['content'])
                        
                        # 處理 JSON 陣列的逗號分隔
                        
                        json.dump(data, sys.stdout, ensure_ascii=False)
                        sys.stdout.write('\n')
        except FileNotFoundError:
            sys.stderr.write(f"Error: File {filepath} not found.\n")
        except Exception as e:
            sys.stderr.write(f"Error processing {filepath}: {e}\n")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.stderr.write("Usage: ./plurk2json.py file1.php file2.php ... > output.json\n")
        sys.exit(1)
    
    process_plurks(sys.argv[1:])
