#!/usr/bin/env python3

import re, sys, argparse


LI_RE = re.compile(r'^(\s*)<li>\s*\d+\s+.*?T=[^"]*?([^"&]+).*?>([^<]+)</a>')
YAML_TAG_RE = re.compile(r'^( *)([^#:\n][^:]*):')


def parse_stat(filename):
    """Return [(level, tag), ...] in DFS order."""
    order = []
    with open(filename, encoding="utf-8") as f:
        for line in f:
            m = LI_RE.match(line)
            if not m:
                continue

            indent = len(m.group(1))
            tag = m.group(3)

            order.append((indent, tag))
    return order


def parse_yaml(filename):
    """
    Return
        blocks[tag] = [original lines...]
        preamble = lines before first tag
    """

    with open(filename, encoding="utf-8") as f:
        lines = f.readlines()

    blocks = {}
    preamble = []
    current_tag = None
    current_indent = None
    current_block = []
    for line in lines:
        m = YAML_TAG_RE.match(line)
        if m:
            indent = len(m.group(1))
            tag = m.group(2).strip()

            if current_tag is None:
                if not blocks:
                    preamble = current_block
            else:
                blocks[current_tag] = current_block
            current_tag = tag
            current_indent = indent
            current_block = [line]
            continue
        if current_tag is None:
            current_block.append(line)
            continue
        current_block.append(line)
    if current_tag is None:
        preamble = current_block
    else:
        blocks[current_tag] = current_block
    return preamble, blocks


def main():
    parser = argparse.ArgumentParser(
        description='sort tag-hierarchy according to the ordering of an html file',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-t', '--taxonomy', type=str, default='tag-hierarchy.yaml',
        help='Path to tag-hierarchy.yaml')
    parser.add_argument('ordering', type=str,
        help='html file defining ordering')
    args = parser.parse_args()

    stat = parse_stat(args.ordering)
    preamble, blocks = parse_yaml(args.taxonomy)
    sys.stdout.writelines(preamble)
    seen = set()
    for _, tag in stat:
        if tag in blocks:
            assert tag not in seen
            seen.add(tag)
            sys.stdout.writelines(blocks[tag])
        else:
            sys.stdout.writelines(f'# {tag}\n')
    assert seen == set(blocks)

if __name__ == "__main__":
    main()

