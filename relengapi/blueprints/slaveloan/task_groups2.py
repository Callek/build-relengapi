# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


from __future__ import absolute_import

from relengapi.blueprints.slaveloan.model import Loans
from relengapi.blueprints.slaveloan.model import Tasks
from relengapi.lib import badpenny
from relengapi.util.tz import utcnow


def next_tasks(loanid):
    loan = Loans.query.get(loanid)
    loan_state = loan.state
    tasks = Tasks.query.filter(Tasks.for_loan == loanid).all()
    if loan_state == "REQUESTED":
        if not tasks:  # none run yet
            # initial task
            return "file_loan_bug"
    if loan_state == "FILE_BUGZILLA":
        # Prep machine
        pass


def has_incomplete_tasks(loanid):
    tasks = Tasks.query.filter(Tasks.for_loan == loanid).all()
    task_statuses = set([task.status for task in tasks])
    complete_statuses = set(['SUCCESS', 'FAILURE'])
    #  uses set() to check if any states not in above list are present
    #  explicitly set to bool to only return truthy
    return bool(task_statuses - complete_statuses)


def maybe_retry_tasks(loanid):
    tasks = Tasks.query.filter(Tasks.for_loan == loanid).all()
    retried_count = 0
    for t in tasks:
        if t.status in ['SUCCESS', 'FAILURE']:
            continue
        if t.status in ['QUEUED', 'RETRYING']:
            dt = t.status_timestamp
            if (utcnow() - dt).total_seconds() > 1800:
                # Re-Kick the task if it has been pending for 30 minutes.
                retried_count += 1

        if t.status in ['RUNNING']:
            # XXX: Check if task has taken too long to run
            #      based on expected runtime
            pass
        raise ValueError("Unexpected task status %s" % t.status)
    return retried_count


@badpenny.periodic_task(seconds=600)
def reschedule_abandoned_jobs(job_status):
    loans = Loans.query.filter(Loans.status != "COMPLETE").all()
    retried = 0
    for l in loans:
        if has_incomplete_tasks(l.id):
            retried += maybe_retry_tasks(l.id)
    if not retried:
        job_status.log_message("All is well, no tasks retried")
