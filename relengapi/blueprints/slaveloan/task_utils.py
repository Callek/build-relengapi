# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


from __future__ import absolute_import

import uuid

import celery
from flask import current_app
from flask import json
from sqlalchemy.exc import IntegrityError

from relengapi.blueprints.slaveloan.model import Tasks
from relengapi.util import tz


class StatefulTaskMixin(object):

    # hook methods

    def on_task_started(self, args):
        "The machine has just entered this state"
        pass

    def on_task_ended(self, args):
        "The machine is about to leave this state"
        pass


def id_to_uuid_object(value):
    if isinstance(value, basestring):
        return uuid.UUID(value)
    if isinstance(value, (int, long)):
        return uuid.UUID(int=value)
    if isinstance(value, uuid.UUID):
        return value


def args_to_json(*args, **kwargs):
    return json.dumps((args, kwargs))


def update_task_object(session=None, task=None, **kwargs):
    """"Update a task, either passed in or created via kwargs

    Caller is responsible for commiting the SQL session (if no
    session passed also for adding to the session)

    :Parameters:
      - `session` (optional) an SQLAlchemy session object (in case of race condition
                             in getting the task, may have a `rollback` issued)
      - `task` (optional) an ORM of an existing task object (created from kwargs) if missing
      - `\**kwargs\` - valid ORM attributes for the task object

    :return: the modified task ORM object
    """

    if not task:
        if not session:
            raise ValueError("Unable to query for task when not passed a session")
        try:
            task = Tasks.as_unique(session, **kwargs)
        except IntegrityError:  # Try Harder
            session.rollback()
            task = Tasks.as_unique(session, **kwargs)
    else:
        if ('id' in kwargs and task.id and
                not id_to_uuid_object(kwargs['id']) == task.id):
            raise ValueError("Unable to set a new ID for passed"
                             "task instance (id as int %s)" % task.id.int)
    for key in kwargs.keys():
        setattr(task, key, kwargs[key])
    return task


def report_task_state(state, loanid, argsJson=None, abort_if=None):
    if state not in ["RETRYING", "FAILURE", "RUNNING", "SUCCESS"]:
        raise ValueError("Unexpected state %s" % (state,))
    session = current_app.db.session('relengapi')
    task_id = celery.current_task.request.id
    time = tz.utcnow()
    t = update_task_object(session=session,
                           id=task_id,
                           loan_id=loanid,
                           name=celery.current_task.name,
                           status_timestamp=time,
                           argsJson=argsJson)
    if t.status and callable(abort_if) and abort_if(t.status):
        raise Exception("Integrity Error, State should not be %s" % t.status)
    # Set the data we expect to change here
    t = update_task_object(session=session, task=t, status=state,
                           status_timestamp=tz.utcnow())
    session.add(t)
    session.commit()
