from prompts import verify_agent_system_prompt
from verifiagent import verifiagent
from utils import *
import os
import json
from tqdm import tqdm

content_format = """
Question: QUESTION

Answer: ANSWER
"""

logic_content_sol_prompt = """
Context: CONTEXT

Question: QUESTION
Options: OPTION

Solution: SOLUTION
"""

logic_content_prompt = """
Context: CONTEXT

Question: QUESTION
Options: OPTION
"""

proverqa_easy = json.load(open("data/proverQA/dev%2Feasy.json"))
proverqa_med = json.load(open("data/proverQA/dev%2Fmedium.json"))
proverqa_hard = json.load(open("data/proverQA/dev%2Fhard.json"))

proverqa = proverqa_easy[:100] + proverqa_med[:100] + proverqa_hard[:100]

total_cost = 0
results = []
num_max_sample = 10
output_file = "outputs/proverqa_gpt4o_output_with_verifiagent.json"

# Load previous run if exists
if os.path.exists(output_file):
    with open(output_file, "r") as f:
        results = json.load(f)
    print(f"Loaded {len(results)} existing results.")
else:
    print("Starting new ProverQA run...")

for example in tqdm(proverqa):
    if any(res["context"] == example["context"] for res in results):
        print(f"Skipping already processed context: {example['context'][:100]}...")
        continue

    record = {
        "context": example.get("context", ""),
        "question": example.get("question", example.get("problem", "")),
        "output": []
    }

    num_try = 0

    for i in range(1, num_max_sample + 1):
        num_try = i
        output = {}

        try:
            question_prompt = logic_content_prompt\
                .replace('CONTEXT', example['context'])\
                .replace('QUESTION', example['question'])\
                .replace('OPTION', str(example['options'])) + \
                " Show your reasoning process, and present the final answer in the format of Answer: [answer]"

            response, cost = gpt4o_prompt_sample_n(
                "You are an expert in solving logical reasoning problems.",
                question_prompt,
                n=1
            )
            total_cost += cost

            answer_text = response[0]

            verifier_input = logic_content_sol_prompt\
                .replace('CONTEXT', example['context'])\
                .replace('QUESTION', example['question'])\
                .replace('OPTION', str(example['options']))\
                .replace('SOLUTION', answer_text)

            verifier_info = verifiagent(verifier_input, to_print=True)
            total_cost += verifier_info["cost"]

            output["try_idx"] = i
            output["prediction"] = answer_text
            output["verifier_info"] = verifier_info
            output["verifi_result"] = verifier_info["eval_result"]

            record["output"].append(output)
            print(f"Try {i}: {verifier_info['eval_result']}")

            if verifier_info["eval_result"] == "Correct":
                break

        except Exception as e:
            print(f"Error at try {i}: {e}")
            break

    record["max_try"] = num_try
    results.append(record)

    # Save after each example
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"Total Cost so far: ${total_cost:.4f}\n")