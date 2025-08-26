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

data_path = "data/MATH/test"
sample_length = 50
math_data = {}
tasks = ['algebra', 'counting_and_probability', 'geometry', 'intermediate_algebra', 'number_theory', 'prealgebra', 'precalculus']
for task in tasks:
    math_task_data = []
    for file in sorted(os.listdir(data_path + f'/{task}'))[:sample_length]:
        with open(data_path + f'/{task}/{file}') as f:
            math_task_data.append(json.load(f))
    math_data[task] = math_task_data

total_cost = 0
results = []
num_max_sample = 10
output_file = "outputs/math_gpt4o_output_with_verifiagent.json"

# Load existing file if continuing from a previous run
if os.path.exists(output_file):
    with open(output_file, "r") as f:
        results = json.load(f)
    print(f"Loaded {len(results)} existing results.")
else:
    print("Starting new run...")

# Main loop
for task in tasks:
    for example in tqdm(math_data[task]):
        if any(res["question"] == example["problem"] for res in results):
            print(f"Skipping already processed question: {example['problem']}")
            continue

        record = {"question": example["problem"], "output": []}
        num_try = 0

        for i in range(1, num_max_sample + 1):
            num_try = i
            output = {}
            question_prompt = (
                f"Question: {example['problem']}\n"
                "Show your reasoning process, and present the final answer of the problem in LaTeX using a \\boxed{} without any units."
            )

            try:
                response, cost = gpt4o_prompt_sample_n(
                    "You are an expert in solving math problems.", question_prompt, n=1
                )
                total_cost += cost

                answer_text = response[0]
                verifier_input = content_format.replace("QUESTION", example["problem"]).replace("ANSWER", answer_text)

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