import openai

import json
import time
from openai import OpenAI
from functions import *
import sys

from typing_extensions import override
    
ASSISTANTS = {
    "Aristotle": "asst_dKkXGVQWYK7na5sa02Cwipmn",
    "Da Vinci": "asst_mJgHiKoFSUvQExMEiU42sf5h",
    "Newton": "asst_dZqSEMrMtnE1qbDsP9mf3jtR",
    "Cicero": "asst_jq1pEakwfITkZeSTQyzEF9wY",
    "Curie": "asst_wxyuiy9LMe6LuFSsUtdYfdeO"
}

# Socrates
MODERATOR = "asst_MzxFALjIRhsxF1Fm3Iz4yxLz"
            
next_speaker = None

def get_next_speaker(assistant_name):
    return assistant_name

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
    
    def modify_message(self, thread_id, message_id, metadata):
        self.client.beta.threads.messages.update(
            thread_id=thread_id,
            message_id=message_id,
            metadata=metadata
        )
    
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
    

class OpenAIRunManager(object):
    def __init__(self, openai_client, assistant_id, thread_id, is_moderator=False):
        self.openai_client = openai_client
        self.assistant_id = assistant_id
        self.thread_id = thread_id
        self.is_moderator = is_moderator
        self.actions_taken = []
    
    def create_run(self):
        self.ai_run = self.openai_client.create_run(
            assistant_id=self.assistant_id,
            thread_id=self.thread_id
        )
        return self.ai_run

    def get_status(self):
        return self.ai_run.status
    
    def status_queued(self):
        return self.get_status() == "queued"
    
    def status_in_progress(self):
        return self.get_status() == "in_progress"
    
    def status_requires_action(self):
        return self.get_status() == "requires_action"
    
    def status_cancelling(self):
        return self.get_status() == "cancelling"

    def _get_run(self):
        return self.openai_client.retrieve_run(
            thread_id=self.thread_id,
            run_id=self.ai_run.id
        )

    def is_run_active(self):
        return self.ai_run.status not in ["cancelled", "completed", "expired", "failed"]
    
    def handle_action(self):
        # I copied some code from another function; it made it easier to assign self.ai_run to just a local ai_run for now
        ai_run = self.ai_run

        num_fn_calls = self.openai_client.get_num_tool_calls(ai_run)
        if num_fn_calls > 1:
            print("[!] Multiple tool calls detected")

        tools_outputs = []
        run_cancelled = False

        for i in range(num_fn_calls):
            tool_call_id, fn, args = self.openai_client.get_tool_call_info(
                ai_run=ai_run,
                index=i
            )
            fn_call = "{}({})".format(fn, args)
            new_action = Action(fn, args)
            self.actions_taken.append(new_action)

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

                if self.is_moderator:
                    self.next_speaker = args.get("name")
            else:
                print("[-] Canceling the run")
                ai_run = client.cancel_run(
                    thread_id=thread.id,
                    run_id=ai_run.id
                )

                run_cancelled = True
                break
            
        if not run_cancelled:
            ai_run = self.openai_client.submit_tool_outputs(
                thread_id=self.thread_id,
                run_id=self.ai_run.id,
                tool_outputs=tools_outputs
            )

    def poll_run(self):
        while self.is_run_active():
            if self.status_requires_action():
                self.handle_action()
            elif self.status_cancelling():
                # Run is being cancelled
                print("[-] Run is being canceled...")
                pass
            elif self.status_queued():
                # Run is queued
                print("[-] Run is queued...")
            elif self.status_in_progress():
                # Run is still in progress
                print("[-] Run is in progress...")

            time.sleep(1)
            self.ai_run = self._get_run()
            continue

    def get_actions(self):
        return self.actions_taken

if __name__ == "__main__":
    client = AIClient()

    thread = client.create_thread()
    print("Thread ID is: {}".format(thread.id))

    REQUEST_PERMISSION = True

    if len(sys.argv) > 1:
        user_input = sys.argv[1]
    else:
        user_input = input("user > ")

    while user_input not in ["exit", "quit", "q"]:
        if user_input != "pass":
            message = client.create_message(
                role="user",
                thread_id=thread.id,
                content=user_input.strip()
            )

        # Have the moderator decide who speaks next
        run_manager = OpenAIRunManager(
            openai_client=client,
            assistant_id=MODERATOR,
            thread_id=thread.id,
            is_moderator=True
        )
        ai_run = run_manager.create_run()
        run_manager.poll_run()

        print("[+] Done with the Run")

        # Pass the thread to the next speaker
        next_speaker = run_manager.next_speaker
        next_speaker_id = ASSISTANTS.get(next_speaker)

        run_manager = OpenAIRunManager(
            openai_client=client,
            assistant_id=next_speaker_id,
            thread_id=thread.id
        )
        ai_run = run_manager.create_run()
        run_manager.poll_run()

        # Get message output from this fun
        messages = client.list_messages_from_run(
            thread_id=thread.id,
            run_id=ai_run.id
        )

        for message in json.loads(messages.json()).get('data'):
            client.modify_message(
                thread_id=thread.id,
                message_id=message.get('id'),
                metadata={
                    "name": next_speaker
                }
            )

        message_content = ""
        for message in messages:
            message_content += messages.data[0].content[0].text.value
        print("\{}> {}".format(next_speaker, message_content))

        print("ACTIONS TAKEN:")
        for action in run_manager.get_actions():
            s = action.print_actions()
            print(s)
        
        user_input = input("\n\nuser > ")
