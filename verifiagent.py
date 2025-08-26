import re
from utils import *
from prompts import verify_agent_system_prompt


def verifiagent(datapoint=None, sys_prompt=verify_agent_system_prompt, to_print=True, llm=gpt4o_prompt):
    if to_print:
        print(datapoint)
    messages = [{"role": "system", "content": sys_prompt}, {"role": "user", "content": datapoint}]
    n_calls, n_badcalls, n_tools = 0, 0, 0
    total_cost = 0.0
    eval_result = ''
    info = {}
    log_probs = []
    traj = datapoint
    for i in range(1, 6):
        n_calls += 1
        raw_response, cost = llm(messages)
        response = raw_response.message.content
        log_probs.extend(raw_response.logprobs.content)
        try:
            thought, action = response.split('Action: ')
            traj += '\n' + response
        except:
            n_badcalls += 1
            n_calls += 1
            print('Bad Call:', response)
            raw_response, cost = llm(messages)
            response = raw_response.message.content
            log_probs.extend(raw_response.logprobs.content)
            try:
                thought, action = response.split('Action: ')
                traj += '\n' + response
            except:
                continue
            total_cost += cost
            
        if to_print:
            print(response)
            
        messages.append({"role": "assistant", "content": response})
        
        if 'Search' in action.split('\n')[0]:
            search_query = extract_text(action.split('\n')[0].strip(), key='Search')
            search_result = query_to_perplexica(search_query)
            n_tools += 1
            if to_print:
                print('\nObservation: ', search_result)
            traj += f'\n\nObservation: [{search_result}]\n'
            messages.append({"role": "user", "content": f'The tool execution result is:\n{search_result}'})
        elif 'Python' in action.split('\n')[0] or 'Prover' in action.split('\n')[0]:
            program = extract_code(action)
            program_answer = safe_execute(program)
            n_tools += 1
            if to_print:
                print('\nObservation: ', program_answer)
            traj += f'\n\nObservation: [{program_answer}]\n'
            messages.append({"role": "user", "content": f'The tool execution result is:\n{program_answer}'})
        elif 'Evaluate' in action.split('\n')[0]:
            eval_result = extract_text(action.split('Summarisation:')[0].strip(), key='Evaluate')
            summarisation = action.split('Summarisation:')[1].strip()
            traj += f'\n\nObservation: [Done]'
            if to_print:
                print(f'\nObservation: [Done]')
            break
        else:
            print('Invalid Action:', action)
        i += 1
        total_cost += cost

    tokens = [item.token.strip() for item in log_probs]
    top5_logprobs = [[token.logprob for token in item.top_logprobs] for item in log_probs]
    try:
        idx = tokens.index('Evaluate')
        top5_logprob = top5_logprobs[idx+2]
        conidence_softmax = temperature_scaling(top5_logprob, 5)[0]
    except:
        conidence_softmax = 0.0
    traj += f'\nV_score: {conidence_softmax}'
    print(f'\nV_score: {conidence_softmax}')

    info.update({'n_calls': n_calls, 'n_badcalls': n_badcalls, 'steps': i, 'n_tools': n_tools, 'traj': traj, 'eval_result': eval_result, 'cost': total_cost, 'V_score': conidence_softmax})
    
    return info