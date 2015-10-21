# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from __future__ import absolute_import

import uuid

import mock
import sqlalchemy as sa
from nose.tools import assert_raises
from nose.tools import eq_
from nose.tools import ok_

from relengapi.blueprints.slaveloan.model import Humans
from relengapi.blueprints.slaveloan.model import Loans
from relengapi.blueprints.slaveloan.model import Machines
from relengapi.blueprints.slaveloan.model import Tasks
from relengapi.blueprints.slaveloan.task_utils import args_to_json
from relengapi.blueprints.slaveloan.task_utils import id_to_uuid_object
from relengapi.blueprints.slaveloan.task_utils import update_task_object
from relengapi.lib.testing.context import TestContext
from relengapi.util import tz


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

    task_orms = []
    for t in (  # id, loan_orm, name
             (1L, loans[0], "test_task"),
             ):
        task_orms.append(Tasks(id=t[0], for_loan=t[1], name=t[2]))
    session.add_all(task_orms)
    session.commit()

test_context = TestContext(databases=['relengapi'],
                           db_setup=db_setup)


def test_uuid_object_from_id():
    """Test a uuid that fits into an int for sake of testing all values easily"""
    test_values = [
        '00000000-0000-0000-7fff-ffffffffffff',
        u'00000000-0000-0000-7fff-ffffffffffff',
        9223372036854775807,
        9223372036854775807L,
        uuid.UUID('{00000000-0000-0000-7fff-ffffffffffff}'),
        ]
    for test in test_values:
        ret = id_to_uuid_object(test)
        ok_(isinstance(ret, uuid.UUID),
            "value of type(%s) should now be a UUID object" % type(test))
        eq_(ret.int, 9223372036854775807L,
            "value of type(%s) converted incorrectly to (%s)" % (type(test), repr(ret)))


def test_args_to_json():
    """Test the args_to_json helper method returns useful json"""
    atj = args_to_json
    eq_(atj('foo', 1, u'bar'), '[["foo", 1, "bar"], {}]')
    eq_(atj(foo='bar', id=2L, minion=u'bob'),
        '[[], {"foo": "bar", "id": 2, "minion": "bob"}]')
    eq_(atj('one', foo='bar'), '[["one"], {"foo": "bar"}]')


@test_context
def test_update_task_object_passed_task(app):
    """Test that we can update an existing task object passing task"""
    now = tz.utcnow()
    with app.app_context():
        session = app.db.session('relengapi')
        t = session.query(Tasks).get(1L)
        update_task_object(task=t, status_timestamp=now)
        session.commit()
        eq_(t.status_timestamp, now)


@test_context
def test_update_task_object(app):
    """Test that we can update an existing task object"""
    now = tz.utcnow()
    with app.app_context():
        session = app.db.session('relengapi')
        t = session.query(Tasks).get(1L)
        ok_(t.status_timestamp < now)
        update_task_object(session=session, id=1L, status_timestamp=now)
        session.commit()
        t = session.query(Tasks).get(1L)
        eq_(t.status_timestamp, now)


@test_context
def test_update_task_object_raced(app):
    """Test that a race condition doesn't fail"""
    now = tz.utcnow()
    with app.app_context():
        unique = mock.patch.object(Tasks, 'as_unique')
        unique.start()

        def _stopMockandraise(*args, **kwargs):
            unique.stop()  # No longer patching unique
            # IntegrityError needs values passed, we don't care what they are here.
            raise sa.exc.IntegrityError(None, None, Exception())
        Tasks.as_unique.side_effect = _stopMockandraise
        session = app.db.session('relengapi')
        t = session.query(Tasks).get(1L)
        ok_(t.status_timestamp < now)
        update_task_object(session=session, id=1L, status_timestamp=now)
        session.commit()
        t = session.query(Tasks).get(1L)
        eq_(t.status_timestamp, now)


@test_context
def test_update_task_object_no_session(app):
    """Test that no session and no task doesn't work"""
    now = tz.utcnow()
    uto = update_task_object
    with app.app_context():
        session = app.db.session('relengapi')
        t = session.query(Tasks).get(1L)
        ok_(t.status_timestamp < now)
        assert_raises(ValueError, uto, id=1L, status_timestamp=now)
        session.commit()
        t = session.query(Tasks).get(1L)
        ok_(t.status_timestamp < now)


@test_context
def test_update_task_object_wrong_task(app):
    """Test that no session and no task doesn't work"""
    now = tz.utcnow()
    uto = update_task_object
    with app.app_context():
        session = app.db.session('relengapi')
        t = session.query(Tasks).get(1L)
        ok_(t.status_timestamp < now)
        assert_raises(ValueError, uto, task=t, id=2L, status_timestamp=now)
        session.commit()
        t = session.query(Tasks).get(1L)
        ok_(t.status_timestamp < now)
