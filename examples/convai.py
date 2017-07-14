# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree. An additional grant
# of patent rights can be found in the PATENTS file in the same directory.

from parlai.core.params import ParlaiParser
from parlai.agents.local_human.local_human import LocalHumanAgent
from parlai.core.convai_world import ConvAIWorld, ConvAIDebugAgent


def main():
    parser = ParlaiParser(True, True)
    parser.add_argument('-n', '--num-examples', default=500)
    parser.add_argument('-d', '--display-examples', type='bool', default=False)
    parser.add_argument('-bi', '--bot-id')
    parser.add_argument('-bc', '--bot-capacity', default=-1)
    parser.add_argument('-rbu', '--router-bot-url')
    parser.add_argument('-rbpd', '--router-bot-pull-delay', default=5)
    opt = parser.parse_args()
    print(opt)

    shared = {
        'agents': [
            {
                'class': ConvAIDebugAgent,
                'opt': opt
            }
        ]
    }

    world = ConvAIWorld(opt, None, shared)

    # Show some example dialogs:
    for k in range(int(opt['num_examples'])):
        world.parley()
        if opt['display_examples']:
            print("---")
            print(world.display() + "\n~~")
        if world.epoch_done():
            print("EPOCH DONE")
            break
    world.shutdown()

if __name__ == '__main__':
    main()