##############################################################################
#
# Copyright (c) 2005 Zope Corporation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################
r"""
Multi-database tests
====================

Multi-database support adds the ability to tie multiple databases into a
collection.

Creating a multi-database starts with creating a named DB:

>>> from ZODB.tests.test_storage import MinimalMemoryStorage
>>> from ZODB import DB
>>> db = DB(MinimalMemoryStorage(), database_name='root')

The database name is accessible afterwards and in a newly created collection:

>>> db.database_name
'root'
>>> db.databases        # doctest: +ELLIPSIS
{'root': <ZODB.DB.DB object at ...>}

Adding a new database works like this:

>>> db2 = DB(MinimalMemoryStorage(),
...     database_name='notroot',
...     databases=db.databases)

The new db2 now shares the 'databases' dictionary with db and has two entries:

>>> db2.databases is db.databases
True
>>> len(db2.databases)
2

Trying to insert a database with a name that is already in use will not work:

>>> db3 = DB(MinimalMemoryStorage(),
...     database_name='root',
...     databases=db.databases)
Traceback (most recent call last):
    ...
ValueError: database_name 'root' already in databases

Because that failed, db.databases wasn't changed:

>>> len(db.databases)  # still 2
2

You can (still) get a connection to a database this way:

>>> cn = db.open()
>>> cn                  # doctest: +ELLIPSIS
<Connection at ...>

This is the only connection in this collection right now:

>>> cn.connections      # doctest: +ELLIPSIS
{'root': <Connection at ...>}

Getting a connection to a different database from an existing connection in the
same database collection (this enables 'connection binding' within a given
thread/transaction/context ...):

>>> cn2 = cn.get_connection('notroot')
>>> cn2                  # doctest: +ELLIPSIS
<Connection at ...>

Now there are two connections in that collection:

>>> cn2.connections is cn.connections
True
>>> len(cn2.connections)
2

So long as this database group remains open, the same Connection objects
are returned:

>>> cn.get_connection('root') is cn
True
>>> cn.get_connection('notroot') is cn2
True
>>> cn2.get_connection('root') is cn
True
>>> cn2.get_connection('notroot') is cn2
True

Of course trying to get a connection for a database not in the group raises
an exception:

>>> cn.get_connection('no way')
Traceback (most recent call last):
  ...
KeyError: 'no way'

Clean up:

>>> for a_db in db.databases.values():
...     a_db.close()
"""

from zope.testing import doctest

def test_suite():
    return doctest.DocTestSuite()