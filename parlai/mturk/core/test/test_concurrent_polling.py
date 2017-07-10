# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree. An additional grant
# of patent rights can be found in the PATENTS file in the same directory.
"""
You should run this test in clusters where there is more computing capacity.
"""
import requests
import json
import time
import sys
from joblib import Parallel, delayed

num_concurrent_requests = int(sys.argv[1])
wait_time_between_requests = 1 # in seconds

task_group_id = 'model_evaluator_1499629716'
db_last_message_id = 1000
json_api_endpoint_url = 'https://5lu5k95kwf.execute-api.us-east-1.amazonaws.com/prod/json'

api_endpoint_dict = {
0: {'html_api_endpoint_url': 'https://58ninnnc2m.execute-api.us-east-1.amazonaws.com/prod/html', 'json_api_endpoint_url': 'https://58ninnnc2m.execute-api.us-east-1.amazonaws.com/prod/json'},
1: {'html_api_endpoint_url': 'https://uauq4lutrb.execute-api.us-east-1.amazonaws.com/prod/html', 'json_api_endpoint_url': 'https://uauq4lutrb.execute-api.us-east-1.amazonaws.com/prod/json'},
2: {'html_api_endpoint_url': 'https://5e8w4484p6.execute-api.us-east-1.amazonaws.com/prod/html', 'json_api_endpoint_url': 'https://5e8w4484p6.execute-api.us-east-1.amazonaws.com/prod/json'},
3: {'html_api_endpoint_url': 'https://mhgx7hfl66.execute-api.us-east-1.amazonaws.com/prod/html', 'json_api_endpoint_url': 'https://mhgx7hfl66.execute-api.us-east-1.amazonaws.com/prod/json'},
4: {'html_api_endpoint_url': 'https://hpw2wxtu47.execute-api.us-east-1.amazonaws.com/prod/html', 'json_api_endpoint_url': 'https://hpw2wxtu47.execute-api.us-east-1.amazonaws.com/prod/json'}
}

global test_thread
def test_thread(thread_id):
    print("Thread "+str(thread_id)+" is on.")
    count = 0
    avg_elapsed = 0
    while True:
        count += 1
        params = {
            'method_name': 'get_new_messages',
            'task_group_id': task_group_id,
            'last_message_id': db_last_message_id,
        }
        response = requests.get(api_endpoint_dict[thread_id % 5]['json_api_endpoint_url'], params=params, allow_redirects=False, timeout=30)
        try:
            ret = json.loads(response.json())
            avg_elapsed = (avg_elapsed * (count - 1) + response.elapsed.total_seconds()) / count
            print("Thread "+str(thread_id)+": Count: "+str(count)+" Success: "+str(ret)+" Elapsed time: "+str(avg_elapsed))
            time.sleep(wait_time_between_requests)
        except Exception as e:
            print(response.content)
            raise e

results = Parallel(n_jobs=num_concurrent_requests, backend='threading')(delayed(test_thread)(thread_id) for thread_id in range(num_concurrent_requests))