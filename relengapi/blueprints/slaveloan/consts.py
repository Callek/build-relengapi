# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from collections import namedtuple

TASK_STATES = ['SUCCESS', 'FAILURE', 'QUEUED', 'RETRYING', 'RUNNING']
SUCCESS_STATE, FAIL_STATE, QUEUED_STATE, RETRYING_STATE = STATES
SUCCESSFUL_STATES = [SUCCESS_STATE]
FAILED_STATES = [FAIL_STATE]
UNFINISHED_STATES = [QUEUED_STATE, RETRYING_STATE, RUNNING_STATE]
ACTIVE_STATES = [RUNNING_STATE]

LOAN_STATES = [
    "REQUESTED",
    "FILE_LOAN_BUG",
    "NEED_AWS_SYSTEM",
    "NEED_VPN_ACCESS",
    "FIXUP_MACHINE_DNS",
    "BMO_SETUP_TRACKING_BUG",
    
]