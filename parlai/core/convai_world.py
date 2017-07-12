# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree. An additional grant
# of patent rights can be found in the PATENTS file in the same directory.

from parlai.core.worlds import World
from parlai.core.agents import create_agent_from_shared
from parlai.core.worlds import validate

import requests
import os
import json
import time


class ConvAIWorld(World):
    """This world send messages from agents (client bots)  back and forth to ConvAI Router Bot.
    Agents created dynamically when new conversation is started. Each agent agent conducts one conversation.
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
        self.bot_capacity = opt.get('bot_capacity')
        self.bot_url = os.path.join(self.router_bot_url, self.bot_id)

    def __get_updates(self):
        res = requests.get(os.path.join(self.bot_url, 'getUpdates'))
        return res.json()

    def __send_message(self, observation, chat):
        if self._is_end_of_conversation(observation['text']):
            data = {
                'text': '/end',
                'evaluation': {
                    'quality': int(input("How do you evaluate quality of conversation (form 1 to 10)? ")),
                    'breadth': int(input("How do you evaluate breadth of conversation (form 1 to 10)? ")),
                    'engagement': int(input("How do you evaluate engagement of conversation (form 1 to 10)? "))
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
        return message == '/end' or message == ''

    @staticmethod
    def _get_chat_id(message):
        return message['message']['chat']['id']

    @staticmethod
    def _get_message_text(message):
        raw_text = message['message']['text'].replace('\\', '/')
        return json.loads(raw_text)['text']

    @staticmethod
    def _strip_start_message(message):
        return message.replace('/start ', '')

    def _init_chat(self, chat):
        agent = create_agent_from_shared(self.shared["agents"][0])
        self.chats[chat] = agent
        self.agents.append(agent)
        print("New chat #%s created and corresponding agent added." % chat)
        return agent

    def _cleanup_chat(self, chat):
        agent = self.chats.pop(chat, None)
        self.agents.remove(agent)
        print("Chat #% is ended and corresponding agent is removed.")
        return agent

    def _cleanup_chats(self, chats):
        for chat in chats:
            self._cleanup_chat(chat)

    def parley(self):
        print("ConvAIWorld:parley " + "-" * 100)
        acts = []
        msgs = self.__get_updates()
        current_chats = {}
        for msg in msgs:
            print("Proceed message: %s" % msg)
            text = self._get_message_text(msg)
            chat = self._get_chat_id(msg)
            episode_done = False
            agent = None
            if self._is_begin_of_conversation(text):
                print("Message recognised as start of new conversation #%s" % chat)
                if 0 <= int(self.bot_capacity) > len(self.agents):
                    agent = self._init_chat(chat)
                    text = self._strip_start_message(text)
                else:
                    print("Can't start new conversation #%s due to bot capacity limit reached." % chat)
            elif self._is_end_of_conversation(text):
                print("Message recognised as end of conversation #%s" % chat)
                agent = self._cleanup_chat(chat)
                episode_done = True
            else:
                agent = self.chats[chat]
                if agent is not None:
                    print("Message was recognized as part of chat #%s" % chat)
                else:
                    print("Message wasn't recognized as part of any chat. Message skipped.")

            if agent is not None:
                m = {
                    'id': 'RouterBot#%s' % chat,
                    'text': text,
                    'episode_done': episode_done
                }
                print("Send message to agent: %s" % m)
                agent.observe(validate(m))
                acts.append(m)
                current_chats[chat] = agent

        chats_to_cleanup = []
        for (chat, agent) in current_chats.items():
            act = validate(agent.act())
            print("Send response from agent for conversation %s: %s" % (chat, act))
            self.__send_message(act, chat)
            acts.append(act)
            if self._is_end_of_conversation(act['text']) or act['episode_done']:
                chats_to_cleanup.append(chat)
        self._cleanup_chats(chats_to_cleanup)
        print("Sleep for %s seconds before new round of conversation" % self.router_bot_pull_delay)
        time.sleep(self.router_bot_pull_delay)

    def __len__(self):
        return len(self.chats.values())

    def __iter__(self):
        return iter(self.chats.values())

    def shutdown(self):
        for (chat, agent) in self.chats.items():
            agent.shutdown()
