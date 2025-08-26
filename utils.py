import func_timeout
import z3
from z3 import *
import requests
from openai import OpenAI
import re
import numpy as np

client = OpenAI(
    api_key="<OpenAI-API-Key>",
)

def gpt4o_prompt(messages):
    got_result = False
    while not got_result:
        try:
            response = client.chat.completions.create(
              model="gpt-4o",
              messages = messages,
              temperature=0,
              logprobs=True,
              top_logprobs=5,
            )
            got_result = True
        except Exception:
            time.sleep(1)

    prompt_cost = (response.usage.prompt_tokens / 1000000) * 2.5
    completion_cost = (response.usage.completion_tokens / 1000000) * 10
    
    total_cost = prompt_cost + completion_cost
    # print(f"Total cost for gpt-4o: ${total_cost:.4f}\n")
    return response.choices[0], total_cost

def gpt4o_prompt_sample_n(sys_content, content, n=10):
    got_result = False
    while not got_result:
        try:
            response = client.chat.completions.create(
              model="gpt-4o",
              messages = [{"role": "system", "content": sys_content}, {"role": "user", "content": content}],
              temperature=0.7,
              n=n
            )
            got_result = True
        except Exception:
            time.sleep(1)

    prompt_cost = (response.usage.prompt_tokens / 1000000) * 2.5
    completion_cost = (response.usage.completion_tokens / 1000000) * 10
    
    total_cost = prompt_cost + completion_cost
    # print(f"Total cost for gpt-4o: ${total_cost:.4f}\n")
    return [res.message.content.strip() for res in response.choices], total_cost

def temperature_scaling(logits, temperature):
    logits = np.array(logits)
    logits /= temperature

    # apply softmax
    logits -= logits.max()
    logits = logits - np.log(np.sum(np.exp(logits)))
    smx = np.exp(logits)
    return smx

def extract_text(text, key):
    if key == 'Search':
        match = re.search(r'Use Search Engine\[(.*?)\]', text)
    elif key == 'Evaluate':
        match = re.search(r'Evaluate\[(.*?)\]', text)
    else:
        match = text
    if match:
        return match.group(1).strip()
    else:
        return text

def extract_code(text):
    lines = text.split('\n')
    in_code_block = False
    code_lines = []
    
    for line in lines:
        if line.strip() == '```' or line.strip().startswith('```python'):
            in_code_block = not in_code_block
        elif in_code_block:
            code_lines.append(line)
            
    return '\n'.join(code_lines)

def check_model(solver):
    res = solver.check()
    if res == sat:
        return 'sat'
    elif res == unsat:
        return 'unsat'
    else:
        return 'unsolvable'

def check_constraint(solver, c):
    pos_res = solver.check(c)
    neg_res = solver.check(Not(c))

    if (pos_res == sat) and (neg_res == unsat):
        return 'Agree'
    elif (pos_res == unsat) and (neg_res == sat):
        return 'Contradict'
    elif (pos_res == unknown) or (neg_res == unknown):
        return 'unsolvable'
    else:
        return 'Uncertain'

def safe_execute(code_string: str, keys=None):
    if code_string.startswith('```python'):
        code_string = extract_code(code_string)
    def execute(x):
        try:
            exec(x)
            locals_ = locals()
            if keys is None:
                return locals_.get('ans', None)
            else:
                return [locals_.get(k, None) for k in keys]
        except Exception:
            return None
    try:
        ans = func_timeout.func_timeout(5, execute, args=(code_string,))
    except func_timeout.FunctionTimedOut:
        ans = ''

    return ans

def query_to_perplexica(query):
    url = 'http://localhost:3001/api/search'
    
    message = {
        "chatModel": {
            "provider": "openai",
            "model": "gpt-4o-mini"
        },
        "embeddingModel": {
            "provider": "openai",
            "model": "text-embedding-3-small"
        },
        "focusMode": "webSearch",
        "query": query,
        "history": [
            ["human", query]
        ]
    }

    response = requests.post(url, json=message)
    # print(response)
    if response.status_code == 200:
        return response.json()['message']
    elif response.status_code == 400:
        raise ValueError('The request is malformed or missing required fields, such as FocusModel or query')
    else:
        raise ValueError('Internal Server Error')