#!/usr/bin/env python3
import argparse, subprocess, sys

def main():
    parser = argparse.ArgumentParser(
        description='select all rows from a table of a database whose id appear in the id_list file',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('db_file',
        help='sqlite3 database file')
    parser.add_argument('target', type=str,
        help='target table and its id column name used for join(), e.g. "student.sid" or "car.plate"')
    parser.add_argument('id_list', type=str,
        help='text file containing a list of id''s, one per line')

    args = parser.parse_args()

    table, col = args.target.rsplit('.', 1)

    # 組裝給 sqlite3 CLI 的指令劇本 (Script)
    sql_script = f'''
CREATE TEMP TABLE _target_ids(id TEXT);
.import '{args.id_list}' _target_ids
.mode json
SELECT {table}.* FROM {table} JOIN _target_ids ON {table}.{col} = _target_ids.id;
'''
    subprocess.run(
        ['sqlite3', args.db_file], input=sql_script, text=True, check=True
    )

if __name__ == '__main__':
    main()
