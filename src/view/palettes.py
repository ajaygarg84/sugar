# Copyright (C) 2008 One Laptop Per Child
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

import os
import statvfs
import logging
from gettext import gettext as _

import gtk

from sugar import env
from sugar import profile
from sugar import activity
from sugar.graphics.palette import Palette
from sugar.graphics.menuitem import MenuItem
from sugar.graphics.icon import Icon
from sugar.graphics import style
from sugar.graphics.xocolor import XoColor

import view.Shell

class BasePalette(Palette):
    def __init__(self, home_activity):
        Palette.__init__(self)

        if home_activity.props.launching:
            home_activity.connect('notify::launching', self._launching_changed_cb)
            self.set_primary_text(_('Starting...'))
        else:
            self.setup_palette()

    def _launching_changed_cb(self, home_activity, pspec):
        if not home_activity.props.launching:
            self.setup_palette()

    def setup_palette(self):
        raise NotImplementedError

class CurrentActivityPalette(BasePalette):
    def __init__(self, home_activity):
        self._home_activity = home_activity
        BasePalette.__init__(self, home_activity)

    def setup_palette(self):
        self.set_primary_text(self._home_activity.get_title())

        menu_item = MenuItem(_('Resume'), 'activity-start')
        menu_item.connect('activate', self.__resume_activate_cb)
        self.menu.append(menu_item)
        menu_item.show()

        """ TODO
        menu_item = MenuItem(_('Share with'), 'zoom-neighborhood')
        #menu_item.connect('activate', self.__share_activate_cb)
        self.menu.append(menu_item)
        menu_item.show()

        menu_item = MenuItem(_('Keep'))
        icon = Icon(icon_name='document-save', icon_size=gtk.ICON_SIZE_MENU,
                xo_color=profile.get_color())
        menu_item.set_image(icon)
        icon.show()
        #menu_item.connect('activate', self.__keep_activate_cb)
        self.menu.append(menu_item)
        menu_item.show()
        """

        separator = gtk.SeparatorMenuItem()
        self.menu.append(separator)
        separator.show()

        menu_item = MenuItem(_('Stop'), 'activity-stop')
        menu_item.connect('activate', self.__stop_activate_cb)
        self.menu.append(menu_item)
        menu_item.show()

    def __resume_activate_cb(self, menu_item):
        self._home_activity.get_window().activate(1)

    def __stop_activate_cb(self, menu_item):
        self._home_activity.get_window().close(1)


class ActivityPalette(Palette):
    def __init__(self, activity_info):
        activity_icon = Icon(file=activity_info.icon,
                             xo_color=profile.get_color(),
                             icon_size=gtk.ICON_SIZE_LARGE_TOOLBAR)

        Palette.__init__(self, primary_text=activity_info.name,
                         icon=activity_icon)

        self._bundle_id = activity_info.bundle_id
        self._version = activity_info.version
        self._favorite = activity_info.favorite

        menu_item = MenuItem(_('Start'), 'activity-start')
        menu_item.connect('activate', self.__start_activate_cb)
        self.menu.append(menu_item)
        menu_item.show()

        """
        menu_item = MenuItem(_('Start with'), 'activity-start')
        menu_item.props.sensitive = False
        #menu_item.connect('activate', self.__start_with_activate_cb)
        self.menu.append(menu_item)
        menu_item.show()
        """

        self._favorite_item = MenuItem('')
        self._favorite_icon = Icon(icon_name='emblem-favorite',
                icon_size=gtk.ICON_SIZE_MENU)
        self._favorite_item.set_image(self._favorite_icon)
        self._favorite_item.connect('activate',
                                    self.__change_favorite_activate_cb)
        self.menu.append(self._favorite_item)
        self._favorite_item.show()

        registry = activity.get_registry()
        registry.connect('activity_changed', self.__activity_changed_cb)
        self._update_favorite_item()

    def _update_favorite_item(self):
        label = self._favorite_item.child
        if self._favorite:
            label.set_text(_('Remove from ring'))
            xo_color = XoColor('%s,%s' % (style.COLOR_WHITE.get_svg(),
                                         style.COLOR_TRANSPARENT.get_svg()))
        else:
	    label.set_text(_('Add to ring'))
            xo_color = profile.get_color()

        self._favorite_icon.props.xo_color = xo_color

    def __start_activate_cb(self, menu_item):
        view.Shell.get_instance().start_activity(self._bundle_id)

    def __change_favorite_activate_cb(self, menu_item):
        registry = activity.get_registry()
        registry.set_activity_favorite(self._bundle_id,
                                       self._version,
                                       not self._favorite)

    def __activity_changed_cb(self, activity_registry, activity_info):
        if activity_info.bundle_id == self._bundle_id and \
               activity_info.version == self._version:
           self._favorite = activity_info.favorite
           self._update_favorite_item()

class JournalPalette(BasePalette):
    def __init__(self, home_activity):
        self._home_activity = home_activity
        self._progress_bar = None
        self._free_space_label = None

        BasePalette.__init__(self, home_activity)

    def setup_palette(self):
        self.set_primary_text(self._home_activity.get_title())

        vbox = gtk.VBox()
        self.set_content(vbox)
        vbox.show()

        self._progress_bar = gtk.ProgressBar()
        vbox.add(self._progress_bar)
        self._progress_bar.show()

        self._free_space_label = gtk.Label()
        self._free_space_label.set_alignment(0.5, 0.5)
        vbox.add(self._free_space_label)
        self._free_space_label.show()

        self.connect('popup', self.__popup_cb)

        menu_item = MenuItem(_('Show contents'))

        icon = Icon(file=self._home_activity.get_icon_path(),
                icon_size=gtk.ICON_SIZE_MENU,
                xo_color=self._home_activity.get_icon_color())
        menu_item.set_image(icon)
        icon.show()

        menu_item.connect('activate', self.__open_activate_cb)
        self.menu.append(menu_item)
        menu_item.show()

    def __open_activate_cb(self, menu_item):
        self._home_activity.get_window().activate(1)

    def __popup_cb(self, palette):
        # TODO: we should be able to ask the datastore this info, as that's the
        # component that knows about mount points.
        stat = os.statvfs(env.get_profile_path())
        free_space = stat[statvfs.F_BSIZE] * stat[statvfs.F_BAVAIL]
        total_space = stat[statvfs.F_BSIZE] * stat[statvfs.F_BLOCKS]

        fraction = (total_space - free_space) / float(total_space)
        self._progress_bar.props.fraction = fraction
        self._free_space_label.props.label = _('%(free_space)d MB Free') % \
                {'free_space': free_space / (1024 * 1024)}
