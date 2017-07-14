# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree. An additional grant
# of patent rights can be found in the PATENTS file in the same directory.

from parlai.core.worlds import World, DialogPartnerWorld, display_messages
from parlai.core.agents import Agent, create_agent_from_shared

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
        self.chat = None
        self.chats = {}
        self.finished_chats = set()
        self.messages = []

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
        agent_info = self.shared["agents"][0]
        if 'opt' in agent_info.keys():
            agent_info['opt'] = {} if agent_info['opt'] is None else agent_info['opt']
            agent_info['opt']['convai_world'] = self
            agent_info['opt']['convai_chat'] = chat

        local_agent = create_agent_from_shared(agent_info)
        remote_agent = ConvAIAgent({'chat': chat})
        world = DialogPartnerWorld({'task': 'ConvAI Dialog'}, [remote_agent, local_agent])
        self.chats[chat] = (remote_agent, local_agent, world)
        print("New world and agents for chat #%s created." % chat)
        return self.chats[chat]

    def cleanup_finished_chat(self, chat):
        if chat in self.finished_chats:
            self.chats.pop(chat, None)[2].shutdown()
            self.finished_chats.remove(chat)
            print("Chat #%s is ended and corresponding agent is removed." % chat)
        else:
            pass

    def cleanup_finished_chats(self):
        for chat in self.finished_chats.copy():
            self.cleanup_finished_chat(chat)

    def pull_new_messages(self):
        while True:
            print("Pull new messages from server")
            msgs = self._get_updates()
            if len(msgs) > 0:
                for msg in msgs:
                    print("Proceed message: %s" % msg)
                    text = self._get_message_text(msg)
                    chat = self._get_chat_id(msg)

                    if self.chats.get(chat, None) is not None:
                        print("Message recognized as part of chat #%s" % chat)
                        self.messages.append((chat, text))
                    elif self._is_begin_of_conversation(text):
                        print("Message recognised as start of new conversation #%s" % chat)
                        if self.bot_capacity == -1 or 0 <= self.bot_capacity > (len(self.chats) - len(self.finished_chats)):
                            self._init_chat(chat)
                            text = self._strip_start_message(text)
                            self.messages.append((chat, text))
                        else:
                            print("Can't start new conversation #%s due to bot capacity limit reached." % chat)
                    else:
                        print("Message wasn't recognized as part of any chat. Message skipped.")
                if len(self.messages) > 0:
                    break
            print("No new messages. Sleep for %s seconds before new try." % self.router_bot_pull_delay)
            time.sleep(self.router_bot_pull_delay)

    def parley(self):
        print("\n" + "-" * 100 + "\nParley\n"+"-"*100+"\n")
        if len(self.messages) == 0:
            self.pull_new_messages()

        (chat, text) = self.messages.pop(0)
        episode_done = self._is_end_of_conversation(text)
        (remote_agent, local_agent, world) = self.chats.get(chat, (None, None, None))

        if remote_agent is not None and local_agent is not None and world is not None:
            self.chat = chat
            remote_agent.text = text
            remote_agent.episode_done = episode_done
            '''
            Do message exchange between agents
            '''
            world.parley()
            '''
            Send response to server
            '''
            observation = remote_agent.observation
            if self._is_end_of_conversation(observation['text']) or observation['episode_done']:
                episode_done = True
            else:
                pass
            if self._is_skip_response(observation['text']):
                print("Skip response from agent for conversation #%s" % chat)
            else:
                print("Send response from agent for conversation #%s: %s" % (chat, observation))
                self._send_message(observation, chat)
        else:
            print("Message wasn't recognized as part of any chat. Message skipped.")

        if episode_done:
            self.finished_chats.add(chat)
            self.cleanup_finished_chat(chat)

    def display(self):
        if self.chat in self.chats.keys():
            return self.chats[self.chat][2].display()
        else:
            return ''

    def shutdown(self):
        print("Shutdown all chats")
        for chat in self.chats.keys():
            self.chats[chat][2].shutdown()
            if chat not in self.finished_chats:
                self._send_message({'text': '/end'}, chat)

    def get_chats(self):
        return self.chats.keys()

    def get_finished_chats(self):
        return self.finished_chats

    def get_world(self, chat):
        return self.chats[chat][2]


class ConvAIAgent(Agent):
    def __init__(self, opt, shared=None):
        super().__init__(opt, shared)
        self.id = "MasterBot#%s" % opt['chat']
        self.text = None
        self.observation = None
        self.episode_done = False

    def act(self):
        return {
            'id': self.id,
            'text': self.text,
            'episode_done': self.episode_done
        }


class ConvAIDebugAgent(Agent):
    def __init__(self, opt, shared=None):
        super().__init__(opt)
        if 'convai_chat' not in opt.keys():
            raise Exception("You must provide parameter 'convai_chat'")
        else:
            self.convai_chat = opt['convai_chat']
            self.id = 'ConvAiDebugAgent#%s' % self.convai_chat

        if 'convai_wold' not in opt.keys() or opt['convai_world'] is None:
            raise Exception("You must provide parameter 'convai_world'")
        else:
            self.convai_world = opt['convai_world']

        self.text = 'Nothing to say yet!'
        self.episode_done = False

    def observe(self, observation):
        self.observation = observation
        self.episode_done = observation['episode_done']
        text = observation['text']
        if self.episode_done:
            self.text = '/end'
        elif text == "$desc":
            self.text = "Total chats: %s\nFinished chats: %s\nCurrnet chat: %s" % (len(self.convai_world.chats), len(self.convai_world.finished_chats), self.convai_world.chat)
        elif text == "$end":
            self.text = "/end"
            self.episode_done = True
        elif text == "$ls":
            res = []
            for chat in self.convai_world.chats.keys():
                status = "Finished" if chat in self.convai_world.finished_chats else "Active"
                res.append((chat, status))
            self.text = str(res)
        elif text == "$cleanup":
            self.text = str(self.convai_world.finished_chats)
            self.convai_world.cleanup_finished_chats()
        elif text == "$chat":
            self.text = "Current chat id is %s" % self.convai_world.chat
        else:
            self.text = 'I love you, %s!' % observation['id']

        print(display_messages([observation]))

    def act(self):
        reply = {
            'id': self.getID(),
            'text': self.text,
            'episode_done': self.episode_done
        }
        return reply

