#!/usr/bin/env python3
import sys, json, argparse, random, re, boto3

def get_args():
    parser = argparse.ArgumentParser(description='Plurk Semantic Exploration Tool (Phase 1)',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('file', nargs='?', type=argparse.FileType('r'), default=sys.stdin,
                        help='Input JSONL file (default: stdin)')
    parser.add_argument('-p', '--percentage', type=float, default=3.0,
                        help='Sampling percentage (e.g., 8 for 8%%)')
    parser.add_argument('-b', '--batch', type=int, default=10,
                        help='Batch size for LLM processing')
    parser.add_argument('-m', '--model', type=str, default='openai.gpt-oss-120b-1:0',
                        help='Bedrock model ID')
    return parser.parse_args()

def extract_id(url):
    return url.strip().rsplit('/', 1)[-1]

def call_bedrock(batch_data, model_id):

    client = boto3.client('bedrock-runtime', region_name='us-east-1')
    
    prompt_text = '''
        你是一位語言分析專家。 請分析以下社群媒體貼文，
        為每篇貼文設定 0 至 3 個觀念性關鍵詞， 包含
        「隱私」、「裝置自主權」、「資訊安全」、「AI」、
        「認知作戰」、「國有器官」、「」
        例如數位隱私、 認知作戰、 憲政體制、 國有器官、 維修權等等。
        另外， 也考慮以下關鍵詞： 「好笑」、 「健康」、 「哲學」、 「實用工具」。

        你的輸出將直接被 regex 處理， 所以請務必輸出一個二維 JSON 陣列：
        [["id_A", "tag_A1", "tag_A2"], ..]]
        除了空格類字元外，不要有其他任何額外的輸出。

        如果貼文文字資訊不足 (例如僅包含圖片或網址) 而無法設定關鍵詞，
        或是沒有特別明顯的主題， 則仍將該 ID 置於陣列中，
        該筆資料構成單一元素的陣列。

        輸入資料：
    '''
    
    input_payload = []
    for item in batch_data:
        post_id = extract_id(item.get('url', ''))
        content = item.get('text_only', '')
        input_payload.append({'id': post_id, 'text': content})
    
    prompt_text += json.dumps(input_payload, ensure_ascii=False, indent=2)
    prompt_text += '\n\nJSON Output:'

    native_request = {
        'service_tier': 'flex',
        'messages': [{'role': 'user', 'content': prompt_text}],
        # 'max_tokens': 4096,
        # 'temperature': 0.2,
        # 設定推論參數。使用較低的 Temperature 以增加結果的一致性。
        # 'top_p': 0.9,
    }

    response = client.invoke_model(
        modelId=model_id,
        body=json.dumps(native_request)
    )
    response_body = response.get("body").read()
    try:
        response_body = json.loads(response_body)
    except Exception as e:
        sys.stderr.write(f'API Error: {e}\n')
        return [response_body]
    result_text = response_body['choices'][0]['message']['content']
    k = result_text.rfind('</reasoning>')
    if k >= 0:
        result_text = result_text[k+len('</reasoning>'):]
    json_match = re.search(r'(\[\s*\[.*?\]\s*\])', result_text, re.DOTALL)
    # print('\n\n' + json_match.group(1))
    try:
        return json.loads(json_match.group(1)) if json_match else [result_text]
    except Exception as e:
        sys.stderr.write(f'API Error: {e}\n')
        return [json_match.group(1)]

def main():
    args = get_args()
    
    # 讀取並執行隨機抽樣
    all_lines = [json.loads(line) for line in args.file if line.strip()]
    sample_size = max(1, int(len(all_lines) * (args.percentage / 100)))
    sampled_data = random.sample(all_lines, sample_size)
    
    sys.stderr.write(f'Sampled {len(sampled_data)} records (out of {len(all_lines)}).\n')

    count = len(sampled_data)
    for i in range(0, count, args.batch):
        current_batch = sampled_data[i : i + args.batch]
        results = call_bedrock(current_batch, args.model)
        j = i + args.batch
        if j >= count: j = count
        ids = ' '.join([extract_id(sampled_data[k]['url']) for k in range(i, j)])
        print(f'# {i:>4} {ids}')
        for res in results:
            # 直接輸出 JSON 陣列至 stdout
            print(json.dumps(res, ensure_ascii=False))

if __name__ == '__main__':
    main()
