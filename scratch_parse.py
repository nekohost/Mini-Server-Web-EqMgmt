import json
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

log_path = r'C:\Users\dooly\.gemini\antigravity-ide\brain\d7e3fa76-f605-4e5c-b8f0-2e8134f025af\.system_generated\logs\transcript.jsonl'
with open(log_path, 'r', encoding='utf-8') as f:
    for line in f:
        data = json.loads(line)
        if data.get('type') == 'USER_INPUT' and '<USER_REQUEST>' in data.get('content', ''):
            req = data['content'].split('<USER_REQUEST>')[1].split('</USER_REQUEST>')[0].strip()
            print(f"USER ({data.get('created_at')}): {req[:100].replace(chr(10), ' ')}")
        elif data.get('type') == 'PLANNER_RESPONSE' and not data.get('tool_calls') and data.get('content'):
            print(f"AI ({data.get('created_at')}): {data.get('content')[:100].replace(chr(10), ' ')}")
