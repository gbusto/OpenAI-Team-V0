import openai

import json
import time
from openai import OpenAI
from functions import *
import sys

from typing_extensions import override

class Action(object):
    def __init__(self, action_fn, action_args):
        self.action_fn = action_fn
        self.action_args = action_args

    def print_actions(self):
        s  = "Function: {}\n".format(self.action_fn)
        s += "Args:"
        for arg in self.action_args:
            s += "\n- {}: {}".format(arg, self.action_args.get(arg))

        return s
    

class MyAssistant(object):
    def __init__(self, name, assistant_id):
        self.name = name
        self.assistant_id = assistant_id


class Comms(object):
    def __init__(self):
        pass

    def send(self, message):
        pass

    def recv(self, prompt="user> "):
        response = input(prompt)
        return response.strip()
    

class OpenAIRunManager(object):
    def __init__(self, ai_run):
        self.ai_run = ai_run


class AIClient(object):
    def __init__(self):
        self.client = OpenAI()
        self.ai_run = None

    def retrieve_assistant(self, assistant_id):
        asst = self.client.beta.assistants.retrieve(assistant_id)
        return asst
    
    def create_thread(self):
        return self.client.beta.threads.create()
    
    def retrieve_thread(self, thread_id):
        thread = self.client.beta.threads.retrieve(thread_id)
        return thread
    
    def create_message(self, role, thread_id, content):
        message = self.client.beta.threads.messages.create(
            thread_id=thread_id,
            role=role,
            content=content
        )
        return message
    
    def list_messages(self, thread_id):
        messages = self.client.beta.threads.messages.list(
            thread_id=thread_id,
        )
        return messages
        
    def list_messages_from_run(self, thread_id, run_id):
        messages = self.client.beta.threads.messages.list(
            thread_id=thread_id,
            run_id=run_id
        )
        return messages

    def create_run(self, assistant_id, thread_id):
        ai_run = self.client.beta.threads.runs.create_and_poll(
            thread_id=thread_id,
            assistant_id=assistant_id
        )
        return ai_run
        
    def cancel_run(self, thread_id, run_id):
        ai_run = self.client.beta.threads.runs.cancel(
            thread_id=thread_id,
            run_id=run_id
        )

        return ai_run

    def is_run_active(self, ai_run):
        return ai_run.status not in ["cancelled", "completed", "expired", "failed"]
    
    def run_requires_action(self, ai_run):
        return ai_run.status == "requires_action"
    
    def get_num_tool_calls(self, ai_run):
        return len(ai_run.required_action.submit_tool_outputs.tool_calls)
    
    def get_tool_call_info(self, ai_run, index):
        tool_call_id = ai_run.required_action.submit_tool_outputs.tool_calls[index].id
        fn = ai_run.required_action.submit_tool_outputs.tool_calls[index].function.name
        args = json.loads(ai_run.required_action.submit_tool_outputs.tool_calls[index].function.arguments)
        return tool_call_id, fn, args
    
    def submit_tool_outputs(self, thread_id, run_id, tool_outputs):
        ai_run = self.client.beta.threads.runs.submit_tool_outputs(
            thread_id=thread_id,
            run_id=run_id,
            tool_outputs=tool_outputs
        )

        return ai_run
    
    def retrieve_run(self, thread_id, run_id):
        ai_run = self.client.beta.threads.runs.retrieve(
            thread_id=thread_id,
            run_id=run_id
        )
        return ai_run


next_speaker = None

def update_next_speaker(assistant_id):
    next_speaker = assistant_id

client = AIClient()

assistant = client.retrieve_assistant("asst_jS9Ena6cvET0JVGNhKo3SdMJ")
# assistant2 = client.retrieve_assistant("")
# moderator = client.retrieve_assistant("")

thread = client.create_thread()
print("Thread ID is: {}".format(thread.id))

REQUEST_PERMISSION = True

if len(sys.argv) > 1:
    user_input = sys.argv[1]
else:
    user_input = input("user > ")

while user_input not in ["exit", "quit", "q"]:
    actions_taken = []

    message = client.create_message(
        role="user",
        thread_id=thread.id,
        content=user_input.strip()
    )

    ai_run = client.create_run(
        thread_id=thread.id,
        assistant_id=assistant.id,
    )

    while client.is_run_active(ai_run):
        if client.run_requires_action(ai_run):
            num_fn_calls = client.get_num_tool_calls(ai_run)
            if num_fn_calls > 1:
                print("[!] Multiple tool calls detected!")

            tools_outputs = []
            run_cancelled = False

            for i in range(num_fn_calls):
                tool_call_id, fn, args = client.get_tool_call_info(
                    ai_run=ai_run,
                    index=i
                )
                fn_call = "{}({})".format(fn, args)
                new_action = Action(fn, args)
                actions_taken.append(new_action)

                print("[-] Required action: {}".format(fn_call))
                if REQUEST_PERMISSION:
                    response = input("Allow action? [y/N] ")
                else:
                    response = "Y"
                if response in ["y", "Y"]:
                    print("[-] Running function {}".format(fn_call))
                    results = eval(fn_call)
                    print("Results:\n{}".format(str(results)[:100]))

                    print("[-] Ran function {}. Now submitting results".format(fn_call))

                    tools_outputs.append({
                        "tool_call_id": tool_call_id,
                        "output": json.dumps(results)
                    })
                else:
                    print("[-] Canceling the run")
                    ai_run = client.cancel_run(
                        thread_id=thread.id,
                        run_id=ai_run.id
                    )

                    run_cancelled = True
                    break
                
            if not run_cancelled:
                ai_run = client.submit_tool_outputs(
                    thread_id=thread.id,
                    run_id=ai_run.id,
                    tool_outputs=tools_outputs
                )

            continue

        elif ai_run.status == "cancelling":
            print("[-] Run is being cancelled...")

        elif ai_run.status == "in_progress":
            print("[-] Run is in progress...")

        elif ai_run.status == "queued":
            print("[-] Run is queued...")

        time.sleep(1)
        ai_run = client.retrieve_run(
            thread_id=thread.id,
            run_id=ai_run.id
        )

    print("[+] Done with the Run")

    messages = client.list_messages_from_run(
        thread_id=thread.id,
        run_id=ai_run.id
    )
    message_content = ""
    for message in messages:
        message_content += messages.data[0].content[0].text.value
    print("\nassistant> {}".format(message_content))

    print("ACTIONS TAKEN:")
    for action in actions_taken:
        s = action.print_actions()
        print(s)
    
    user_input = input("\n\nuser > ")
