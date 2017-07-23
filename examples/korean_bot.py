"""
Copyright 2017 Neural Networks and Deep Learning lab, MIPT

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

from parlai.convai.convai_world import ConvAIWorld
from parlai.core.agents import Agent
from parlai.core.worlds import display_messages

import my_search

class KoreanBot(Agent):
    def __init__(self, opt, shared=None):
        super().__init__(opt)
        self.id = 'KoreanBot'
        self.text = 'Nothing to say yet!'
        self.episode_done = False

    def observe(self, observation):
        self.observation = observation
        self.episode_done = observation['episode_done']
        if self.episode_done:
            self.text = '/end'
        else:
            self.text = my_search.search(self.observation['text'])
            if self.text == "":
                self.text = "speak again?"
        print("\t"+display_messages([observation]))

    def act(self):
        reply = {
            'id': self.getID(),
            'text': self.text,
            'episode_done': self.episode_done
        }
        print("\t"+display_messages([reply]))
        return reply


def main():
    opt = {
        'bot_id': "0A36119D-E6C0-4022-962F-5B5BDF21FD97",
        'bot_capacity': -1,
        'router_bot_url': 'https://ipavlov.mipt.ru/nipsrouter/',
        'router_bot_pull_delay': 1
    }

    print(opt)

    shared = {
        'agents': [
            {
                'class': KoreanBot,
                'opt': opt
            }
        ]
    }

    world = ConvAIWorld(opt, None, shared)

    while True:
        try:
            world.parley()
        except Exception as e:
            print("Exception: {}".format(e))


if __name__ == '__main__':
    main()
