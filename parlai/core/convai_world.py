# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree. An additional grant
# of patent rights can be found in the PATENTS file in the same directory.

from parlai.core.worlds import World
from parlai.core.agents import create_agent_from_shared
from parlai.core.worlds import validate
from parlai.core.agents import Agent

import requests
import os
import json
import time


class ConvAIWorld(World):
    """This world send messages from agents (client bots)  back and forth to ConvAI Master Bot.
    Agents created dynamically from shared data when new conversation is started. Each agent conducts one conversation.
    """

    def __init__(self, opt, agents, shared=None):
        super().__init__(opt)

        if shared is None:
            raise RuntimeError("Agents should be provide via 'shared' parameter")

        self.shared = shared
        self.agents = []
        self.acts = []
        self.chats = {}

        self.router_bot_url = opt.get('router_bot_url')

        self.router_bot_pull_delay = int(opt.get('router_bot_pull_delay'))
        if self.router_bot_pull_delay < 1:
            self.router_bot_pull_delay = 1

        self.bot_id = opt.get('bot_id')

        self.bot_capacity = int(opt.get('bot_capacity'))

        self.bot_url = os.path.join(self.router_bot_url, self.bot_id)

    def _get_updates(self):
        res = requests.get(os.path.join(self.bot_url, 'getUpdates'))
        return res.json()

    def _send_message(self, observation, chat):
        if self._is_end_of_conversation(observation['text']):
            data = {
                'text': '/end',
                'evaluation': {
                    'quality': 0,
                    'breadth': 0,
                    'engagement': 0
                }
            }
        else:
            data = {
                'text': observation['text'],
                'evaluation': 0
            }
        message = {
            'chat_id': chat,
            'text': json.dumps(data)
        }

        headers = {
            'Content-Type': 'application/json'
        }

        res = requests.post(os.path.join(self.bot_url, 'sendMessage'), json=message, headers=headers)
        if res.status_code != 200:
            print(res.text)
            res.raise_for_status()

    @staticmethod
    def _is_begin_of_conversation(message):
        return message.startswith('/start ')

    @staticmethod
    def _is_end_of_conversation(message):
        return message == '/end'

    @staticmethod
    def _is_skip_response(message):
        return message == ''

    @staticmethod
    def _get_chat_id(message):
        return message['message']['chat']['id']

    @staticmethod
    def _get_message_text(message):
        return message['message']['text']

    @staticmethod
    def _strip_start_message(message):
        return message.replace('/start ', '')

    def _init_chat(self, chat):
        agent = create_agent_from_shared(self.shared["agents"][0])
        self.chats[chat] = agent
        print("New chat #%s created and corresponding agent added." % chat)
        return agent

    def _cleanup_chats(self, chats):
        for chat in chats:
            self.chats.pop(chat, None)
            print("Chat #%s is ended and corresponding agent is removed." % chat)

    def parley(self):
        print("\n"+"-" * 100+"\n")
        '''
        Send new messages to agents
        '''
        msgs = self._get_updates()
        active_chats = set()
        finished_chats = set()
        acts = []
        agents = []
        for msg in msgs:
            print("Proceed message: %s" % msg)
            text = self._get_message_text(msg)
            chat = self._get_chat_id(msg)
            episode_done = False

            if self._is_begin_of_conversation(text):
                print("Message recognised as start of new conversation #%s" % chat)

                if self.chats.get(chat, None) is not None:
                    print("WARNING: Chat #%s already exists and it will be overwritten!")
                else:
                    pass

                if self.bot_capacity == -1 or 0 <= self.bot_capacity > len(self.chats):
                    self._init_chat(chat)
                    text = self._strip_start_message(text)
                else:
                    print("Can't start new conversation #%s due to bot capacity limit reached." % chat)
            elif self._is_end_of_conversation(text):
                print("Message recognised as end of conversation #%s" % chat)
                episode_done = True
                finished_chats.add(chat)
            else:
                pass

            agent = self.chats.get(chat, None)

            if agent is not None:
                print("Message was recognized as part of chat #%s" % chat)
                active_chats.add(chat)
                stub_agent = StubConvAiAgent({'chat': chat})
                m = {
                    'id': stub_agent.id,
                    'text': text,
                    'episode_done': episode_done
                }
                print("Send new message from chat #%s to corresponding agent %s" % (chat, agent))
                agent.observe(validate(m))
                acts.append(m)
                agents.append(stub_agent)
            else:
                print("Message wasn't recognized as part of any chat. Message skipped.")

        '''
        Collect responses from agents
        '''
        for chat in active_chats.difference(finished_chats):
            agent = self.chats.get(chat, None)
            if agent is not None:
                act = validate(agent.act())

                if self._is_end_of_conversation(act['text']) or act['episode_done']:
                    finished_chats.add(chat)
                else:
                    pass

                if self._is_skip_response(act['text']):
                    print("Skip response from agent for conversation #%s" % chat)
                else:
                    print("Send response from agent for conversation #%s: %s" % (chat, act))
                    self._send_message(act, chat)
                    acts.append(act)
                    agents.append(agent)

        self.acts = acts
        self.agents = agents
        '''
        Cleanup finished chats
        '''
        self._cleanup_chats(finished_chats)
        '''
        Sleep before new pull request 
        '''
        print("Sleep for %s seconds before new round of conversation" % self.router_bot_pull_delay)
        time.sleep(self.router_bot_pull_delay)

    def __len__(self):
        return len(self.chats.values())

    def __iter__(self):
        return iter(self.chats.values())

    def shutdown(self):
        for (chat, agent) in self.chats.items():
            agent.shutdown()


class StubConvAiAgent(Agent):
    def __init__(self, opt, shared=None):
        super().__init__(opt, shared)
        self.id = "MasterBot#%s" % opt['chat']

    def act(self):
        pass

    def observe(self, observation):
        pass

