#!/usr/bin/env python3
import argparse, os, re, sqlite3, sys

def extract_plurks(file_path):
    plurks = []

    pattern = re.compile(
        r"<li>(<a\s+href='https://www\.plurk\.com/p/([a-z0-9]+)'>(\d{6}-\d{4})</a>.*?)(</li>)?$",
        re.IGNORECASE,
    )
    f = open(file_path, 'r', encoding='utf-8')
    for line in f:
        match = pattern.search(line)
        if match:
            full_li = match.group(1).strip()
            id = match.group(2)
            ts = match.group(3)
            plurks.append((id, ts, full_li))
    return plurks

def main():
    parser = argparse.ArgumentParser(
        description='Extract Plurk posts from HTML/PHP files and import them into SQLite.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-d', '--database', default='plurk_tags.db',
        help='Path to the SQLite database file',
    )
    parser.add_argument('files', nargs='+',
        help='HTML or PHP files containing plurks in <li> format',
    )
    args = parser.parse_args()

    conn = sqlite3.connect(args.database)
    cursor = conn.cursor()
    for file_path in args.files:
        plurks = extract_plurks(file_path)
        N = len(plurks)
        print(f'{N:4d} {file_path}')
        cursor.executemany(
            'INSERT OR REPLACE INTO plurk (id, ts, content) VALUES (?, ?, ?)',
            plurks,
        )
        conn.commit()
    conn.close()

if __name__ == '__main__':
    main()
