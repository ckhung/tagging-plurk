#!/usr/bin/env python3
import sys, os, re, argparse, yaml

def parse_yaml_hierarchy(data, parent_ancestors=None):
    if parent_ancestors is None:
        parent_ancestors = []
    ancestor_map = {}
    if isinstance(data, dict):
        for tag, children in data.items():
            assert tag not in ancestor_map, f"Duplicate tag definition found: {tag}"
            ancestor_map[tag] = parent_ancestors.copy()
            if children is not None:
                current_ancestors = parent_ancestors + [tag]
                child_map = parse_yaml_hierarchy(children, current_ancestors)
                ancestor_map.update(child_map)
    return ancestor_map

def main():
    parser = argparse.ArgumentParser(
        description='Cleanup LLM output tags based on YAML hierarchy.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-t', '--taxonomy', type=str, default='tag-hierarchy.yaml',
        help='Path to tag-hierarchy.yaml')
    parser.add_argument('tagged_files', nargs='+', type=str,
        help='files containing LLM output tags')
    args = parser.parse_args()

    # Stage 1: Load taxonomy file
    with open(args.taxonomy, "r", encoding="utf-8") as f:
        raw_yaml = yaml.safe_load(f)
    ancestor_map = parse_yaml_hierarchy(raw_yaml)
    valid_tags = ancestor_map.keys()

    # Regex matcher for input lines: "<id> <timestamp> %% <tags...>"
    line_pattern = re.compile(r"^(?P<prefix>.*\s%%\s)(?P<tags>.*)$")

    # Stage 2: Process files sequentially
    for file_path in args.tagged_files:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for line in lines:
            line_str = line.rstrip("\r\n")
            match = line_pattern.match(line_str)
            if not match:
                print(line_str)
                continue
            prefix = match.group("prefix")
            raw_tags = match.group("tags").strip().split()
            raw_tags = [t for t in raw_tags if t in valid_tags]
            retained_tags = []
            for tag in raw_tags:
                if tag in retained_tags or any(tag in ancestor_map[x] for x in raw_tags):
                    continue
                retained_tags.append(tag)

            # Format back to output line
            tag_str = " ".join(retained_tags) if retained_tags else "∅"
            print(f"{prefix}{tag_str}")

if __name__ == "__main__":
    main()
