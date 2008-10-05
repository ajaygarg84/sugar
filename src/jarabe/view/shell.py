# Copyright (C) 2006-2007 Red Hat, Inc.
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

import gobject
import gtk
import wnck

from jarabe.view.launchwindow import LaunchWindow
from jarabe.model import shell

class Shell(gobject.GObject):
    def __init__(self):
        gobject.GObject.__init__(self)

        self._model = shell.get_model()
        self._launchers = {}
        self._screen = wnck.screen_get_default()
        self._screen_rotation = 0

        from jarabe.view.keyhandler import KeyHandler
        self._key_handler = KeyHandler()

        from jarabe.frame import frame
        self._frame = frame.get_instance()

        from jarabe.desktop.homewindow import HomeWindow
        self.home_window = HomeWindow()
        self.home_window.show()

        self._model.connect('launch-started', self.__launch_started_cb)
        self._model.connect('launch-failed', self.__launch_failed_cb)
        self._model.connect('launch-completed', self.__launch_completed_cb)

    def __launch_started_cb(self, home_model, home_activity):
        if home_activity.is_journal():
            return

        launch_window = LaunchWindow(home_activity)
        launch_window.show()

        self._launchers[home_activity.get_activity_id()] = launch_window
        self._model.set_zoom_level(shell.ShellModel.ZOOM_ACTIVITY)

    def __launch_failed_cb(self, home_model, home_activity):
        if not home_activity.is_journal():
            self._destroy_launcher(home_activity)

    def __launch_completed_cb(self, home_model, home_activity):
        if not home_activity.is_journal():
            self._destroy_launcher(home_activity)

    def _destroy_launcher(self, home_activity):
        activity_id = home_activity.get_activity_id()

        if activity_id in self._launchers:
            self._launchers[activity_id].destroy()
            del self._launchers[activity_id]
        else:
            logging.error('Launcher for %s is missing' % activity_id)

    def get_frame(self):
        return self._frame

    def set_zoom_level(self, level):
        if level == self._model.get_zoom_level():
            logging.debug('Already in the level %r' % level)
            return

        if level == shell.ShellModel.ZOOM_ACTIVITY:
            active_activity = self._model.get_active_activity()
            active_activity.get_window().activate(gtk.get_current_event_time())
        else:
            self._model.set_zoom_level(level)
            self._screen.toggle_showing_desktop(True)

_instance = None

def get_instance():
    global _instance
    if not _instance:
        _instance = Shell()
    return _instance
