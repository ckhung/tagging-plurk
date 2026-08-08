#!/usr/bin/python3
# convert "plurk rss json" to html

# for f in *.xml ; do xq-python . $f > ${f/%xml/json} ; done
# python3 ~/public_html/g/p/prj2html.py *.json > ~/new.html 
# 詳見 https://newtoypia.blogspot.com/2021/09/xml-js-jq-rss.html


import argparse, json, re
from warnings import warn

parser = argparse.ArgumentParser(
    description='把 「xml-js 所轉出的噗浪 rss => json」 再轉成 html',
    formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('rssjson', nargs='*', help='rssjson1 rssjson2 ...')
args = parser.parse_args()


verbs = {
    '分享': 'shares',
    '問': 'asks',
    '愛': 'loves',
    '喜歡': 'likes',
    '好奇': 'wonders',
    '已經': 'has',
    '想要': 'wants',
    '打算': 'will',
    '期待': 'wishes',
    '希望': 'hopes',
    '覺得': 'feels',
    '說': 'says',
    '需要': 'needs',
    '討厭': 'hates',
    '轉噗': 'replurks',
    '转噗': 'replurks',
    '警告!': 'warns',
    '玩': 'plays',
    'replurks': 'replurks',
}

allplurks = {}
for rjfn in args.rssjson:
    with open(rjfn) as f:
        data = json.load(f)
    if not ('feed' in data and 'entry' in data['feed']):
        warn(f'warning: file "{rjfn}" ignored because it does not have ".feed.entry"')
        continue
    for e in data['feed']['entry']:
        pid = e['link']['@href']
        datetime = re.match(r'^20(\d\d)-(\d\d)-(\d\d)T(\d\d):(\d\d)', e['published'])
        content = re.match(r'^(\w+)\s+(\S+)\s+(.*)', e['content']['#text'])
        v = content.group(2)    # verb
        if not v in verbs:
            warn(f'verb "{v}" not recognized')
            v = '說'
        allplurks[pid] = {
            'year': datetime.group(1),
            'month': datetime.group(2),
            'text': '<li><a href=\'https://www.plurk.com{}\'>{}{}{}-{}{}</a> {} <span class=\'qualifier {}\'>{}</span> {}'.format(
                pid, datetime.group(1), datetime.group(2), datetime.group(3), datetime.group(4), datetime.group(5),
                content.group(1), verbs[v], v, content.group(3)
            )
        }

last_month = ''
for p in sorted(allplurks.keys(), reverse=True) :
    entry = allplurks[p]
    if entry['month'] != last_month:
        print('''
</ul>

<h3 class='month'>{}年{}月</h3>

<ul class='plurk'>
'''.format(entry['year'], entry['month']) )
    last_month = entry['month']
    print(entry['text'])
