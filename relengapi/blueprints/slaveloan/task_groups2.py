# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


from __future__ import absolute_import

import structlog
from flask import current_app
from flask import json
from werkzeug.local import LocalProxy

from relengapi.blueprints.slaveloan.model import Loans
from relengapi.blueprints.slaveloan.model import Tasks
from relengapi.util.tz import utcnow
from relengapi.util.tz import tasks

logger = structlog.get_logger()


def get_task_name(task_obj):
    if isinstance(task_obj, LocalProxy):
        task_obj = task_obj._get_current_object()
    task_module = task_obj.__class__.__module__
    task_name = task_obj.__name__
    return "%s.%s" % (task_module, task_name)


def has_task_and_successful(task, matchlist):
    task_name = get_task_name(task)
    retval = None
    for possible_task in matchlist:
        if possible_task.name is not task_name:
            continue
        if possible_task.status is not "SUCCESS":
            return False
        return True


def next_tasks(loanid):
    loan = Loans.query.get(loanid)
    loan_state = loan.state
    tasks = Tasks.query.filter(Tasks.for_loan == loanid)
    tasks = tasks.order_by(sa.desc(Tasks.status_timestamp))
    if loan_state == "REQUESTED":
        if not tasks:  # none run yet
            # initial task
            return tasks.bmo_file_loan_bug
        if has_task_and_successful(tasks.bmo_file_loan_bug, tasks):
            return 
    if loan_state == "FILE_BUGZILLA":
        # Prep machine
        pass


def next_tasks2(loanid):
    loan = Loans.query.get(loanid)
    loan_state = loan.state
    requested = loan.requested_machine
    aws = slave_mappings.is_aws_serviceable(requested)
    gpo = slave_mappings.needs_gpo(requested)
    if loan_state == "REQUESTED":
        if aws:
            yield get_task_name(tasks.bmo_file_loan_bug)
            yield get_task_name(tasks.create_aws_system)
            yield get_task_name(tasks.set_aws_machine_info)
            yield get_task_name(tasks.manual_add_to_vpn)
            yield get_task_name(tasks.bmo_set_tracking_bug)
        else:  # Not AWS
            yield get_task_name(tasks.bmo_file_loan_bug)
            yield get_task_name()


def has_incomplete_tasks(loanid):
    logger.debug("loanid: %s" % repr(loanid))
    tasks = Tasks.query.filter_by(loan_id=loanid).all()
    task_statuses = set([task.status for task in tasks])
    complete_statuses = set(['SUCCESS', 'FAILURE'])
    #  uses set() to check if any states not in above list are present
    #  explicitly set to bool to only return truthy
    return bool(task_statuses - complete_statuses)


def maybe_retry_tasks(loanid):
    tasks = Tasks.query.filter_by(loan_id=loanid).all()
    retried_count = 0
    for t in tasks:
        if t.status in ['SUCCESS', 'FAILURE']:
            continue
        if t.status in ['QUEUED', 'RETRYING']:
            dt = t.status_timestamp
            if (utcnow() - dt).total_seconds() > 1800:
                # Re-Kick the task if it has been pending for 30 minutes.
                retried_count += 1
                args, kwargs = json.loads(t.argsJson)
                current_app.celery.send_task(
                    task_id=str(t.uuid.hex),
                    name=t.name,
                    args=args,
                    kwargs=kwargs,
                )
            continue
        if t.status in ['RUNNING']:
            # XXX: Check if task has taken too long to run
            #      based on expected runtime and kill it
            continue
        raise ValueError("Unexpected task status %s" % t.status)
    return retried_count
