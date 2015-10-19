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

logger = structlog.get_logger()


class StateMachine(object):

    statesByName = {}

    # external interface

    def __init__(self, loanid):
        self.loanid = loanid
        self.state = None

    def get_loan(self, session=None):
        """Must pass a session if you intend to modify the object"""
        if session:
            query = session.query(Loans)
        else:
            query = Loans.query
        return query.get(self.loanid)

    def handle_event(self, event, args):
        "Act on an event for this loan, specified by name"
        self.state = self._make_state_instance()
        try:
            self.state.handle_event(event, args)
        finally:
            self.state = None

    def conditional_goto_state(self, old_state, new_state):
        """
        Transition to NEW_STATE only if the device is in OLD_STATE.  Returns
        True on success, False on failure.
        """
        self.state = self._make_state_instance()
        try:
            current_state = self.state.state_name
            if current_state != 'unknown' and old_state != self.state.state_name:
                return False
            self.goto_state(new_state)
            return True
        finally:
            self.state = None

    # virtual methods

    def read_state(self):
        return self.get_loan().state

    def write_state(self, new_state):
        session = current_app.db.session('relengapi')
        loan = self.get_loan(session)
        loan.state = new_state
        session.commit()

    # state mechanics

    def goto_state(self, new_state_name_or_class):
        """Transition the machine to a new state.  The caller should return
        immediately after calling this method."""
        if isinstance(new_state_name_or_class, type) and issubclass(new_state_name_or_class, State):
            new_state_name_or_class = new_state_name_or_class.state_name

        self.state.on_exit()

        # only log actual state changes, rather than re-entries of the same state
        if self.state.state_name != new_state_name_or_class:
            logger.info('entering state %s' % (new_state_name_or_class,))

        self.state = self._make_state_instance(new_state_name_or_class)
        self.write_state(new_state_name_or_class)

        self.state.on_entry()

    # decorator

    @classmethod
    def state_class(cls, state_class):
        """Decorator -- decorates a class as a state for loans."""
        cls.statesByName[state_class.__name__] = state_class
        state_class.state_name = state_class.__name__
        return state_class

    # utilities

    def _make_state_instance(self, state_name=None):
        if not state_name:
            state_name = self.read_state()
        state_cls = self.statesByName.get(state_name)
        if not state_cls:
            state_cls = self.statesByName['unknown']
        return state_cls(self)


class State(object):

    def __init__(self, machine):
        self.machine = machine

    def handle_event(self, event, args):
        handler = self._event_methods.get(event)
        if handler:
            handler(self, args)
        else:
            logger.warning("ignored event %s in state %s" % (event, self.__class__.__name__))

    # hook methods

    def on_entry(self):
        "The machine has just entered this state"
        pass

    def on_exit(self):
        "The machine is about to leave this state"
        pass

    # magic mechanics

    class __metaclass__(type):
        def __new__(meta, classname, bases, classDict):
            cls = type.__new__(meta, classname, bases, classDict)

            # extract API event methods, using dir() to get parent-class methods
            eventMethods = dict([(n[3:], getattr(cls, n))
                                 for n in dir(cls) if n.startswith('on_')])
            del eventMethods['entry']
            del eventMethods['exit']
            cls._event_methods = eventMethods

            return cls


@StateMachine.state_class
class unknown(State):
    """The loan is in an unknown state, awaiting instructions"""


def _get_machine(loanid):
    return StateMachine(loanid=loanid)


def get_task_name(task_obj):
    if isinstance(task_obj, LocalProxy):
        task_obj = task_obj._get_current_object()
    task_module = task_obj.__class__.__module__
    task_name = task_obj.__name__
    return "%s.%s" % (task_module, task_name)

"""
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
"""


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
