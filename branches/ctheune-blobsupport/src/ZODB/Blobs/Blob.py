
import os
import time
import tempfile

from zope.interface import implements

from ZODB.Blobs.interfaces import IBlob
from ZODB.Blobs.exceptions import BlobError
from ZODB import utils
import transaction
from transaction.interfaces import IDataManager
from persistent import Persistent

class Blob(Persistent):
 
    implements(IBlob)

    _p_blob_readers = 0
    _p_blob_writers = 0
    _p_blob_uncommitted = None
    _p_blob_data = None

    def open(self, mode="r"):
        """Returns a file(-like) object for handling the blob data."""
        result = None

        if (mode.startswith("r") or mode=="U"):
            if self._current_filename() is None:
                raise BlobError, "Blob does not exist."

            if self._p_blob_writers != 0:
                raise BlobError, "Already opened for writing."

            self._p_blob_readers += 1
            result = BlobFile(self._current_filename(), mode, self)

        if mode.startswith("w"):
            if self._p_blob_readers != 0:
                raise BlobError, "Already opened for reading."

            if self._p_blob_uncommitted is None:
                self._p_blob_uncommitted = utils.mktemp()

            self._p_blob_writers += 1
            result = BlobFile(self._p_blob_uncommitted, mode, self)

        if mode.startswith("a"):
            if self._p_blob_readers != 0:
                raise BlobError, "Already opened for reading."

            if self._p_blob_uncommitted is None:
                # Create a new working copy
                self._p_blob_uncommitted = utils.mktmp()
                uncommitted = BlobFile(self._p_blob_uncommitted, mode, self)
                utils.cp(file(self._p_blob_data), uncommitted)
                uncommitted.seek(0)
            else:
                # Re-use existing working copy
                uncommitted = BlobFile(self._p_blob_uncommitted, mode, self)

            self._p_blob_writers +=1
            result = uncommitted

        if result is not None:

            # we register ourselves as a data manager with the
            # transaction machinery in order to be notified of
            # commit/vote/abort events.  We do this because at
            # transaction boundaries, we need to fix up _p_ reference
            # counts that keep track of open readers and writers and
            # close any writable filehandles we've opened.

            dm = BlobDataManager(self, result)
            transaction.get().register(dm)

        return result

    # utility methods

    def _current_filename(self):
        return self._p_blob_uncommitted or self._p_blob_data

    def _change(self):
        self._p_changed = 1

    def _rc_clear(self):
        self._p_blob_readers = 0
        self._p_blob_writers = 0

    def _rc_decref(self, mode):
        if mode.startswith('r') or mode == 'U':
            self._p_blob_readers = max(0, self._p_blob_readers - 1)
        elif mode.startswith('w') or mode.startswith('a'):
            self._p_blob_writers = max(0, self._p_blob_writers - 1)
        else:
            raise AssertionError, 'Unknown mode %s' % mode

    def _get_refcounts(self):
        # used by unit tests
        return self._p_blob_readers, self._p_blob_writers

class BlobDataManager:
    """Special data manager to handle transaction boundaries for blobs.

    Blobs need some special care taking on transaction boundaries. As

    a) the ghost objects might get reused, the _p_ reader and writer
       refcount attributes must be set to a consistent state
    b) the file objects might get passed out of the thread/transaction
       and must deny any relationship to the original blob.
    c) writable blob filehandles must be closed at the end of a txn so
       as to not allow reuse between two transactions.

    """

    implements(IDataManager)

    def __init__(self, blob, filehandle):
        self.blob = blob
        self.filehandle = filehandle
        self.subtransaction = False
        self.sortkey = time.time()

    def abort_sub(self, transaction):
        pass

    def commit_sub(self, transaction):
        pass

    def tpc_begin(self, transaction, subtransaction=False):
        self.subtransaction = subtransaction

    def tpc_abort(self, transaction):
        pass

    def tpc_finish(self, transaction):
        self.subtransaction = False

    def tpc_vote(self, transaction):
        pass
                
    def commit(self, object, transaction):
        if not self.subtransaction:
            self.blob._rc_clear() # clear all blob refcounts
            self.filehandle.close()

    def abort(self, object, transaction):
        if not self.subtransaction:
            self.blob._rc_clear()
            self.filehandle.close()

    def sortKey(self):
        return self.sortkey

    def beforeCompletion(self, transaction):
        pass

    def afterCompletion(self, transaction):
        pass

class BlobFile(file):
    """ A BlobFile is a file that can be used within a transaction boundary """
    

    # XXX those files should be created in the same partition as
    # the storage later puts them to avoid copying them ...

    def __init__(self, name, mode, blob):
        super(BlobFile, self).__init__(name, mode)
        self.blob = blob
        self.streamsize = 1<<16

    def write(self, data):
        super(BlobFile, self).write(data)
        self.blob._change()

    def writelines(self, lines):
        super(BlobFile, self).writelines(lines)
        self.blob._change()

    def truncate(self, size=0):
        super(BlobFile, self).truncate(size)
        self.blob._change()
        
    def close(self):
        self.blob._rc_decref(self.mode)
        super(BlobFile, self).close()

    def next(self):
        data = self.read(self.streamsize)
        if not data:
            if self.blob is not None:
                self.blob._rc_decref(self.mode)
            raise StopIteration
        return data

