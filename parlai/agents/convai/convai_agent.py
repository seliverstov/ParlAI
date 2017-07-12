# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree. An additional grant
# of patent rights can be found in the PATENTS file in the same directory.

from parlai.core.agents import Agent

import requests
import os
import json
import time


class ConvAIAgent(Agent):

    def __init__(self, opt, shared=None):
        super().__init__(opt, shared)
        self.bot_id = opt.get('bot_id')
        self.router_bot_url = opt.get('router_bot_url')
        self.bot_url = os.path.join(self.router_bot_url,self.bot_id)
        self.id = 'ConvAIAgent, chat#'
        self.chat_id = None
        self.episode_done = False

    def _cleanup(self):
        self.chat_id = None
        self.episode_done = False

    def act(self):
        reply = {}
        if self.episode_done:
            reply = {
                'text': '',
                'episode_done': True,
                'id': self.id
            }
            self._cleanup()
        else:
            while True:
                res = requests.get(os.path.join(self.bot_url,'getUpdates'))
                for m in res.json():
                    if self.chat_id is None and m['message']['text'].startswith('/start '):
                        self.chat_id = m['message']['chat']['id']
                        self.id += str(self.chat_id)

                    if m['message']['chat']['id'] == self.chat_id:
                        print("Accept message: %s" % m)
                        reply['text'] = m['message']['text']
                        reply['id'] = self.id
                        return reply
                    else:
                        if self.chat_id is None:
                            print("Dialog not started yet. Ignore message: %s" % m)
                        else:
                            print("Multiple dialogues are not allowed. Ignore message: %s" % m)
                time.sleep(5)
        return reply

    def observe(self, observation):
        if self.chat_id is None:
            print("Dialog not started yet. Ignore observation: %s" % observation)
            return observation

        self.observation = observation

        message = {
            'chat_id': self.chat_id
        }

        data = {
            'text': observation['text'],
            'evaluation': 0
        }

        if observation['text'] == '/end' or observation['text'] == '' or observation['episode_done']:
            data['text'] = '/end'
            data['evaluation'] = {
                'quality': int(input("How do you evaluate quality of conversation (form 1 to 10)? ")),
                'breadth': int(input("How do you evaluate breadth of conversation (form 1 to 10)? ")),
                'engagement': int(input("How do you evaluate engagement of conversation (form 1 to 10)? "))
            }
            self.chat_id = None
            self.episode_done = True
        else:
            data['evaluation'] = 0

        message['text'] = json.dumps(data)

        headers = {
            'Content-Type': 'application/json'
        }
        print(message)
        res = requests.post(os.path.join(self.bot_url, 'sendMessage'), json=message, headers=headers)
        if res.status_code != 200:
            print(res.text)
            res.raise_for_status()
        return observation


