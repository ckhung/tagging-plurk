#!/usr/bin/env python3

import argparse, os, sys, re, hashlib, traceback
from openai import OpenAI

def parse_args():
    parser = argparse.ArgumentParser(description='CLI to invoke LLM, requires env vars OPENAI_BASE_URL and OPENAI_API_KEY.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-m', '--model', default='openai.gpt-oss-120b',
        help='Model ID')
    parser.add_argument('-s', '--system', action='append',
        help='System prompt files')
    parser.add_argument('-u', '--user', action='append',
        help='User prompt files')
    parser.add_argument('-k', '--knowledge', action='append',
        help='Knowledge/reference files')
    parser.add_argument('-v', '--vars', default='',
        help='Comma-separated key=value pairs for interpolation/substitution')
    parser.add_argument('--style', default='chat',
        help='chat or responses?')
    parser.add_argument('--list-models', action=argparse.BooleanOptionalAction, default=False,
        help='List available models for this end point')
    parser.add_argument('--keep-ref-path', action=argparse.BooleanOptionalAction, default=False,
        help='Keep leading path of reference files')
    parser.add_argument('--raw-output', action=argparse.BooleanOptionalAction, default=False,
        help='Print raw output from response')
    parser.add_argument('-d', '--diag-prefix', type=str, default='',
        help='Print diagnostic info (along with LLM output!) using this prefix. Empty string means omitting diagnostics.')
    parser.add_argument('--prompt-cache-key', type=str, default='',
        help='prompt cache key to reduce cost and processing time')
    return parser.parse_args()

def read_and_concat(file_list, keep_path=False, attachment=''):
    text = ''
    if file_list is None:
        return text
    for fn in file_list:
        name = fn if keep_path else os.path.basename(fn)
        text += f'\n\n===== {attachment}{name} =====\n'
        with open(fn, 'r', encoding='utf-8') as fh:
            text += fh.read()
        text += f'\n===== end of {name} =====\n'
    return text

def apply_variables(text, vars_str):
    if not vars_str:
        return text
    for item in vars_str.split(','):
        key, value = item.split('=', 1)
        key = key.strip()
        value = value.strip()
        text = text.replace(
            '{{' + key + '}}',
            value
        )
    return text

def build_messages(system_content, user_content):
    messages = []
    if system_content.strip():
        messages.append( {
            "role": "system",
            "content": system_content
        } )
    messages.append( {
        "role": "user",
        "content": user_content
    } )
    return messages

def main():

    args = parse_args()
    # print("MODEL:", repr(args.model), "\nREGION:", os.environ['OPENAI_BASE_URL'], file=sys.stderr)

    assert os.environ.get("OPENAI_API_KEY"), 'Missing OPENAI_API_KEY environment variable'
    assert os.environ.get("OPENAI_BASE_URL"), 'Missing OPENAI_BASE_URL environment variable'
    system_content = read_and_concat(args.system, keep_path=args.keep_ref_path)
    user_content = read_and_concat(args.user, keep_path=args.keep_ref_path)
    user_content += read_and_concat(args.knowledge, keep_path=args.keep_ref_path, attachment="attachment: ")
    system_content = apply_variables(system_content, args.vars)
    user_content = apply_variables(user_content, args.vars)
    messages = build_messages(system_content, user_content)
    client = OpenAI()
    # 會自動讀： OPENAI_API_KEY OPENAI_BASE_URL
    if args.list_models:
        for m in client.models.list():
            print(m.id)
        sys.exit(0)
    try:
        if args.style == 'chat':
            extra_body = {'prompt_cache_key': args.prompt_cache_key} if args.prompt_cache_key else {}
            response = client.chat.completions.create(
                model=args.model,
                messages=messages,
                store=False,
                # service_tier='flex',
                extra_body=extra_body,
            )
            if args.diag_prefix:
                # n = 8
                # print(f'{args.diag_prefix} [First few lines and their sha256sums:]')
                # for s in messages[0]['content'].splitlines()[:n]:
                #     h = hashlib.sha256(s.encode('utf-8')).hexdigest()[:8]
                #     if len(s) > 80: s = s[:80]
                #     print(f'{args.diag_prefix} {h} {s}')
                if hasattr(response, 'usage') and response.usage:
                    usage = response.usage
                    cached_tokens = getattr(getattr(usage, 'prompt_tokens_details', None), 'cached_tokens', 0)
                    print(f'{args.diag_prefix} [Usage] Prompt Tokens: {usage.prompt_tokens} (Cached: {cached_tokens}), Completion Tokens: {usage.completion_tokens}')
            final_text = (
                response.model_dump_json(indent=2) #, exclude_none=True, exclude_unset=True)
                if args.raw_output
                else response.choices[0].message.content
            )
        elif args.style[:8] == 'response':
            response = client.responses.create(
                model=args.model,
                input=messages,
                store=False,
                # service_tier='flex',
            )
            final_text = json.dumps(response, ensure_ascii=False) if args.raw_output else response.output_text
        else:
            assert False, f'unknown style {args.style}'

    except Exception as e:
        traceback.print_exc()
        sys.exit(1)
    print(final_text)

if __name__ == '__main__':
    main()
