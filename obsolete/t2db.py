#!/usr/bin/env python3
import argparse, os, re, sqlite3, sys

def main():
    parser = argparse.ArgumentParser(
        description='Parse plain text tags file and import into plurk_tag table.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-d', '--database', default='plurk_tags.db',
        help='Path to the SQLite database file')
    parser.add_argument('tag_file',
        help='The text file containing timestamps and tags')
    args = parser.parse_args()

    tag_records = []
    f = open(args.tag_file, 'r', encoding='utf-8')
    for line_num, line in enumerate(f, 1):
        line = line.strip()
        if not line or line.startswith('#'): continue  
        parts = line.split()
        if len(parts) < 2: continue
        ts = parts[0]
        tags = parts[1:]
        for tag in tags:
            tag_records.append((ts, tag))
    f.close()

    conn = sqlite3.connect(args.database)
    cursor = conn.cursor()
    cursor.execute('PRAGMA foreign_keys = ON;')
#    for entry in tag_records:
#        print(entry)
#        cursor.execute(
#            'INSERT OR IGNORE INTO plurk_tag (plurk_ts, tag) VALUES (?, ?)', entry
#        )
    cursor.executemany(
        'INSERT OR IGNORE INTO plurk_tag (plurk_id, tag) VALUES (?, ?)',
        tag_records,
    )
    conn.commit()
    inserted = cursor.rowcount if cursor.rowcount > 0 else len(tag_records)
    print(f'Successfully processed {len(tag_records)} tag-relations into "{args.database}".')
    conn.close()

if __name__ == '__main__':
    main()
