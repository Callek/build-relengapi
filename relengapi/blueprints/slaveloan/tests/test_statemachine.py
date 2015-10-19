# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from __future__ import absolute_import

import mock
from nose.tools import eq_
from nose.tools import ok_

from relengapi.blueprints.slaveloan.model import Humans
from relengapi.blueprints.slaveloan.model import Loans
from relengapi.blueprints.slaveloan.model import Machines
from relengapi.blueprints.slaveloan.statemachine import State
from relengapi.blueprints.slaveloan.statemachine import StateMachine
from relengapi.blueprints.slaveloan.statemachine import unknown
from relengapi.lib.testing.context import TestContext


"""
import sqlalchemy as sa
from flask import json

from relengapi.blueprints.slaveloan.model import History
from relengapi.lib import auth
from relengapi.lib.permissions import p
from relengapi.util import tz
"""


def db_setup(app):
    session = app.db.session('relengapi')
    machines = []
    for m in (("127.0.0.1", "host1.mozilla.org"),):
        machines.append(Machines(ipaddress=m[0], fqdn=m[1]))
    session.add_all(machines)

    humans = []
    for u in (("user1@mozilla.com", "user1@mozilla.com"),):
        humans.append(Humans(ldap=u[0], bugzilla=u[1]))
    session.add_all(humans)

    loans = []
    for l in (  # status, bug, machine, human, state
             ("ACTIVE", 1234001, machines[0], humans[0], "state1"),
             ):
        loans.append(
            Loans(status=l[0], bug_id=l[1], machine=l[2], human=l[3], state=l[4])
            )
    session.add_all(loans)

    session.commit()

test_context = TestContext(databases=['relengapi'],
                           db_setup=db_setup)


@StateMachine.state_class
class state1(State):

    called_on_poke = False

    def on_poke(self, args):
        state1.called_on_poke = True

    def on_goto2(self, args):
        self.machine.goto_state('state2')

    def on_goto2_class(self, args):
        self.machine.goto_state(state2)

    def on_goto_unknown_foobar(self, args):
        self.machine.goto_state('foobar')


@StateMachine.state_class
class state2(State):
    pass


@StateMachine.state_class
class state3(State):
    pass


@test_context
def test_event(app):
    """Test that defined events are called"""
    state1.called_on_poke = False
    with app.app_context():
        sm = StateMachine(loanid=1)
        sm.handle_event('poke', {})
    ok_(state1.called_on_poke)


@test_context
def test_unknown_event(app):
    """Test that an undefined event doesn't break"""
    with app.app_context():
        sm = StateMachine(loanid=1)
        sm.handle_event('never-heard-of-it', {})


@test_context
def test_state_transition(app):
    """Test state transitions with string state"""
    # also tests on_exit and on_entry
    with app.app_context():
        sm = StateMachine(loanid=1)
        with mock.patch.object(state1, 'on_exit') as on_exit:
            with mock.patch.object(state2, 'on_entry') as on_entry:
                sm.handle_event('goto2', {})
                ok_(on_exit.called)
                ok_(on_entry.called)
        eq_(sm.read_state(), 'state2')
        eq_(Loans.query.get(1).state, 'state2')


@test_context
def test_state_transition_class_object(app):
    """Test state transitions with object state"""
    with app.app_context():
        sm = StateMachine(loanid=1)
        with mock.patch.object(state1, 'on_exit') as on_exit:
            with mock.patch.object(state2, 'on_entry') as on_entry:
                sm.handle_event('goto2_class', {})
                ok_(on_exit.called)
                ok_(on_entry.called)
        eq_(sm.read_state(), 'state2')
        eq_(Loans.query.get(1).state, 'state2')


@test_context
def test_state_transition_unknown(app):
    """Test state transitions with unknown state name"""
    with app.app_context():
        sm = StateMachine(loanid=1)
        with mock.patch.object(state1, 'on_exit') as on_exit:
            with mock.patch.object(state2, 'on_entry') as on_entry:
                sm.handle_event('goto_unknown_foobar', {})
                ok_(on_exit.called)
                ok_(not on_entry.called)
        eq_(sm.read_state(), 'foobar')
        eq_(Loans.query.get(1).state, 'foobar')
        # handle_event sets sm.state to None after its done
        ok_(isinstance(sm._make_state_instance(), unknown))


@test_context
def test_state_conditional(app):
    """Test state transitions with conditional state"""
    # also tests on_exit and on_entry
    with app.app_context():
        sm = StateMachine(loanid=1)
        with mock.patch.object(state1, 'on_exit') as on_exit:
            with mock.patch.object(state2, 'on_entry') as on_entry:
                sm.conditional_goto_state('state1', 'state2')
                ok_(on_exit.called)
                ok_(on_entry.called)
        eq_(sm.read_state(), 'state2')
        eq_(Loans.query.get(1).state, 'state2')


@test_context
def test_state_conditional_unknown(app):
    """Test state transitions with conditional state passes on unknown state
    even when the states don't match"""
    # also tests on_exit and on_entry
    with app.app_context():
        sm = StateMachine(loanid=1)
        sm.handle_event('goto_unknown_foobar', {})
        with mock.patch.object(state2, 'on_entry') as on_entry:
            ok_(sm.conditional_goto_state('state1', 'state2'))
            ok_(on_entry.called)
        eq_(sm.read_state(), 'state2')
        eq_(Loans.query.get(1).state, 'state2')


@test_context
def test_state_conditional_failed(app):
    """Test state transitions with conditional state fails when condition unmet"""
    # also tests on_exit and on_entry
    with app.app_context():
        sm = StateMachine(loanid=1)
        with mock.patch.object(state1, 'on_exit') as on_exit:
            with mock.patch.object(state2, 'on_entry') as on_entry:
                ok_(not sm.conditional_goto_state('state2', 'state3'))
                ok_(not on_exit.called)
                ok_(not on_entry.called)
        eq_(sm.read_state(), 'state1')
        eq_(Loans.query.get(1).state, 'state1')
