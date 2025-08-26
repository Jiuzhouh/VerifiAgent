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

with open("data/strategyqa_dev.json", "r") as f:
    sqa = json.load(f)

total_cost = 0
results = []
num_max_sample = 10
output_file = "outputs/strategyqa_gpt4o_output_with_verifiagent.json"

# Load previous results if available
if os.path.exists(output_file):
    with open(output_file, "r") as f:
        results = json.load(f)
    print(f"Loaded {len(results)} existing results.")
else:
    print("Starting new StrategyQA run...")

# Main loop
for example in tqdm(sqa):
    if any(res["question"] == example["question"] for res in results):
        print(f"Skipping already processed question: {example['question']}")
        continue

    record = {"question": example["question"], "output": []}
    num_try = 0

    for i in range(1, num_max_sample + 1):
        num_try = i
        output = {}

        try:
            question_prompt = (
                f"Question: {example['question']}\n"
                "Answer the question with True or False, and show your reasoning process. "
                "Present the final answer in the format of Answer: [answer]"
            )

            response, cost = gpt4o_prompt_sample_n(
                "You are an expert in solving commonsense reasoning problems.",
                question_prompt,
                n=1
            )
            total_cost += cost

            answer_text = response[0].strip()

            verifier_input = content_format.replace("QUESTION", example["question"]).replace("ANSWER", answer_text)

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

    # Save results after each example
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"Total Cost so far: ${total_cost:.4f}\n")