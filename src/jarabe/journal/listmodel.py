# Copyright (C) 2009, Tomeu Vizoso
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import logging

import json
from gi.repository import GObject
from gi.repository import Gtk
from gettext import gettext as _

from sugar3.graphics.xocolor import XoColor
from sugar3.graphics import style
from sugar3 import util

from jarabe.journal import model
from jarabe.journal import misc


DS_DBUS_SERVICE = 'org.laptop.sugar.DataStore'
DS_DBUS_INTERFACE = 'org.laptop.sugar.DataStore'
DS_DBUS_PATH = '/org/laptop/sugar/DataStore'


class ListModel(GObject.GObject, Gtk.TreeModel, Gtk.TreeDragSource):
    __gtype_name__ = 'JournalListModel'

    __gsignals__ = {
        'ready': (GObject.SignalFlags.RUN_FIRST, None, ([])),
        'progress': (GObject.SignalFlags.RUN_FIRST, None, ([])),
    }

    COLUMN_UID = 0
    COLUMN_FAVORITE = 1
    COLUMN_ICON = 2
    COLUMN_ICON_COLOR = 3
    COLUMN_TITLE = 4
    COLUMN_TIMESTAMP = 5
    COLUMN_CREATION_TIME = 6
    COLUMN_FILESIZE = 7
    COLUMN_PROGRESS = 8
    COLUMN_BUDDY_1 = 9
    COLUMN_BUDDY_2 = 10
    COLUMN_BUDDY_3 = 11

    _COLUMN_TYPES = {
        COLUMN_UID: str,
        COLUMN_FAVORITE: bool,
        COLUMN_ICON: str,
        COLUMN_ICON_COLOR: object,
        COLUMN_TITLE: str,
        COLUMN_TIMESTAMP: str,
        COLUMN_CREATION_TIME: str,
        COLUMN_FILESIZE: str,
        COLUMN_PROGRESS: int,
        COLUMN_BUDDY_1: object,
        COLUMN_BUDDY_3: object,
        COLUMN_BUDDY_2: object,
    }

    _PAGE_SIZE = 10

    def __init__(self, query):
        GObject.GObject.__init__(self)

        self._last_requested_index = None
        self._cached_row = None
        self._result_set = model.find(query, ListModel._PAGE_SIZE)
        self._temp_drag_file_path = None

        # HACK: The view will tell us that it is resizing so the model can
        # avoid hitting D-Bus and disk.
        self.view_is_resizing = False

        self._result_set.ready.connect(self.__result_set_ready_cb)
        self._result_set.progress.connect(self.__result_set_progress_cb)

    def __result_set_ready_cb(self, **kwargs):
        self.emit('ready')

    def __result_set_progress_cb(self, **kwargs):
        self.emit('progress')

    def setup(self):
        self._result_set.setup()

    def stop(self):
        self._result_set.stop()

    def get_metadata(self, path):
        return model.get(self[path][ListModel.COLUMN_UID])

    def do_get_n_columns(self):
        return len(ListModel._COLUMN_TYPES)

    def do_get_column_type(self, index):
        return ListModel._COLUMN_TYPES[index]

    def do_iter_n_children(self, iterator):
        if iterator == None:
            return self._result_set.length
        else:
            return 0

    def do_get_value(self, iterator, column):
        if self.view_is_resizing:
            return None

        index = iterator.user_data
        if index == self._last_requested_index:
            return self._cached_row[column]

        if index >= self._result_set.length:
            return None

        self._result_set.seek(index)
        metadata = self._result_set.read()

        self._last_requested_index = index
        self._cached_row = []
        self._cached_row.append(metadata['uid'])
        self._cached_row.append(metadata.get('keep', '0') == '1')
        self._cached_row.append(misc.get_icon_name(metadata))

        if misc.is_activity_bundle(metadata):
            xo_color = XoColor('%s,%s' % (style.COLOR_BUTTON_GREY.get_svg(),
                                          style.COLOR_TRANSPARENT.get_svg()))
        else:
            xo_color = misc.get_icon_color(metadata)
        self._cached_row.append(xo_color)

        title = GObject.markup_escape_text(metadata.get('title',
                                           _('Untitled')))
        self._cached_row.append('<b>%s</b>' % (title, ))

        try:
            timestamp = float(metadata.get('timestamp', 0))
        except (TypeError, ValueError):
            timestamp_content = _('Unknown')
        else:
            timestamp_content = util.timestamp_to_elapsed_string(timestamp)
        self._cached_row.append(timestamp_content)

        try:
            creation_time = float(metadata.get('creation_time'))
        except (TypeError, ValueError):
            self._cached_row.append(_('Unknown'))
        else:
            self._cached_row.append(
                util.timestamp_to_elapsed_string(float(creation_time)))

        try:
            size = int(metadata.get('filesize'))
        except (TypeError, ValueError):
            size = None
        self._cached_row.append(util.format_size(size))

        try:
            progress = int(float(metadata.get('progress', 100)))
        except (TypeError, ValueError):
            progress = 100
        self._cached_row.append(progress)

        buddies = []
        if metadata.get('buddies'):
            try:
                buddies = json.loads(metadata['buddies']).values()
            except json.decoder.JSONDecodeError, exception:
                logging.warning('Cannot decode buddies for %r: %s',
                                metadata['uid'], exception)

        if not isinstance(buddies, list):
            logging.warning('Content of buddies for %r is not a list: %r',
                            metadata['uid'], buddies)
            buddies = []

        for n_ in xrange(0, 3):
            if buddies:
                try:
                    nick, color = buddies.pop(0)
                except (AttributeError, ValueError), exception:
                    logging.warning('Malformed buddies for %r: %s',
                                    metadata['uid'], exception)
                else:
                    self._cached_row.append((nick, XoColor(color)))
                    continue

            self._cached_row.append(None)

        return self._cached_row[column]

    def do_iter_nth_child(self, parent_iter, n):
        return (False, None)

    def do_get_path(self, iterator):
        treepath = Gtk.TreePath((iterator.user_data,))
        return treepath

    def do_get_iter(self, path):
        idx = path.get_indices()[0]
        iterator = Gtk.TreeIter()
        iterator.user_data = idx
        return (True, iterator)

    def do_iter_next(self, iterator):
        idx = iterator.user_data + 1
        if idx >= self._result_set.length:
            iterator.stamp = -1
            return (False, iterator)
        else:
            iterator.user_data = idx
            return (True, iterator)

    def do_get_flags(self):
        return Gtk.TreeModelFlags.ITERS_PERSIST | Gtk.TreeModelFlags.LIST_ONLY

    def do_iter_children(self, iterator):
        return (False, iterator)

    def do_iter_has_child(self, iterator):
        return False

    def do_iter_parent(self, iterator):
        return (False, Gtk.TreeIter())

    def do_drag_data_get(self, path, selection):
        uid = self[path][ListModel.COLUMN_UID]
        target_atom = selection.get_target()
        target_name = target_atom.name()
        if target_name == 'text/uri-list':
            # Get hold of a reference so the temp file doesn't get deleted
            self._temp_drag_file_path = model.get_file(uid)
            logging.debug('putting %r in selection', self._temp_drag_file_path)
            selection.set(target_atom, 8, self._temp_drag_file_path)
            return True
        elif target_name == 'journal-object-id':
            # uid is unicode but Gtk.SelectionData.set() needs str
            selection.set(target_atom, 8, str(uid))
            return True

        return False
