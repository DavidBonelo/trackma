# This file is part of Trackma.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

from gi.repository import Gtk, Gdk, Pango, GObject
from trackma import utils


class ShowListStore(Gtk.ListStore):
    __cols = (
        ('id', int),
        ('title', str),
        ('stat', int),
        ('score', float),
        ('stat-text', str),
        ('score-text', str),
        ('total-eps', int),
        ('subvalue', int),
        ('avail-eps', GObject.TYPE_PYOBJECT),
        ('color', str),
        ('stat-pcent', int),
        ('start', str),
        ('end', str),
        ('my-start', str),
        ('my-end', str),
        ('my-status', str),
        ('status', int),
    )

    def __init__(self, decimals=0, colors=dict()):
        super().__init__(*self.__class__.__columns__())
        self.colors = colors
        self.decimals = decimals
        self.set_sort_column_id(1, Gtk.SortType.ASCENDING)

    @staticmethod
    def format_date(date):
        if date:
            try:
                return date.strftime('%Y-%m-%d')
            except ValueError:
                return '?'
        else:
            return '-'

    @classmethod
    def __columns__(cls):
        return (k for i, k in cls.__cols)

    @classmethod
    def column(cls, key):
        try:
            return cls.__cols.index(next(i for i in cls.__cols if i[0] == key))
        except ValueError:
            return None

    def _get_color(self, show, eps):
        if show.get('queued'):
            return self.colors['is_queued']
        elif eps and max(eps) > show['my_progress']:
            return self.colors['new_episode']
        elif show['status'] == utils.STATUS_AIRING:
            return self.colors['is_airing']
        elif show['status'] == utils.STATUS_NOTYET:
            return self.colors['not_aired']
        else:
            return None

    def append(self, show, altname=None, eps=None):
        episodes_str = "{} / {}".format(show['my_progress'],
                                        show['total'] or '?')
        if show['total'] and show['my_progress'] <= show['total']:
            progress = (float(show['my_progress']) / show['total']) * 100
        else:
            progress = 0

        title_str = show['title']
        if altname:
            title_str += " [%s]" % altname

        score_str = "%0.*f" % (self.decimals, show['my_score'])
        aired_eps = utils.estimate_aired_episodes(show)

        if eps:
            available_eps = eps.keys()
        else:
            available_eps = []

        start_date = self.format_date(show['start_date'])
        end_date = self.format_date(show['end_date'])
        my_start_date = self.format_date(show['my_start_date'])
        my_finish_date = self.format_date(show['my_finish_date'])

        row = [show['id'],
               title_str,
               show['my_progress'],
               show['my_score'],
               episodes_str,
               score_str,
               show['total'],
               aired_eps,
               available_eps,
               self._get_color(show, available_eps),
               progress,
               start_date,
               end_date,
               my_start_date,
               my_finish_date,
               show['my_status'],
               show['status']
               ]
        super().append(row)

    def update_or_append(self, show):
        for row in self:
            if int(row[0]) == show['id']:
                self.update(show, row)
                return
        self.append(show)

    def update(self, show, row=None):
        if not row:
            for row in self:
                if int(row[0]) == show['id']:
                    break
        if row and int(row[0]) == show['id']:
            episodes_str = "{} / {}".format(show['my_progress'],
                                            show['total'] or '?')
            row[2] = show['my_progress']
            row[4] = episodes_str

            score_str = "%0.*f" % (self.decimals, show['my_score'])

            row[3] = show['my_score']
            row[5] = score_str
            row[9] = self._get_color(show, row[8])
            row[15] = show['my_status']
        return

        # print("Warning: Show ID not found in ShowView (%d)" % show['id'])

    def update_title(self, show, altname=None):
        for row in self:
            if int(row[0]) == show['id']:
                if altname:
                    title_str = "%s [%s]" % (show['title'], altname)
                else:
                    title_str = show['title']

                row[1] = title_str
                return

    def remove(self, show=None, id=None):
        for row in self:
            if int(row[0]) == (show['id'] if show is not None else id):
                Gtk.ListStore.remove(self, row.iter)
                return

    def playing(self, show, is_playing):
        # Change the color if the show is currently playing
        for row in self:
            if int(row[0]) == show['id']:
                if is_playing:
                    row[9] = self.colors['is_playing']
                else:
                    row[9] = self._get_color(show, row[8])
                return


class ShowListFilter(Gtk.TreeModelFilter):
    def __init__(self, status=None, *args, **kwargs):
        super().__init__(
            *args,
            **kwargs
        )
        self.set_visible_func(self.status_filter)
        self._status = status

    def status_filter(self, model, iter, data):
        return self._status is None or model[iter][15] == self._status

    def get_value(self, obj, key='id'):
        try:
            if type(obj) == Gtk.TreePath:
                obj = self.get_iter(obj)
            if isinstance(key, (str,)):
                key = self.props.child_model.column(key)
            return super().get_value(obj, key)
        except:
            return None


class ShowTreeView(Gtk.TreeView):
    __gsignals__ = {'column-toggled': (GObject.SignalFlags.RUN_LAST,
                                       GObject.TYPE_PYOBJECT, (GObject.TYPE_STRING, GObject.TYPE_BOOLEAN))}

    def __init__(self, colors, visible_columns, progress_style=1):
        Gtk.TreeView.__init__(self)

        self.colors = colors
        self.visible_columns = visible_columns
        self.progress_style = progress_style

        self.set_enable_search(True)
        self.set_search_column(1)
        self.set_property('has-tooltip', True)
        self.connect('query-tooltip', self.show_tooltip)

        self.cols = dict()
        self.available_columns = (
            ('Title', 1),
            ('Progress', 2),
            ('Score', 3),
            ('Percent', 10),
            ('Start', 11),
            ('End', 12),
            ('My start', 13),
            ('My end', 14),
        )

        for (name, sort) in self.available_columns:
            self.cols[name] = Gtk.TreeViewColumn(name)
            self.cols[name].set_sort_column_id(sort)

            # This is a hack to allow for right-clickable header
            label = Gtk.Label(name)
            label.show()
            self.cols[name].set_widget(label)

            self.append_column(self.cols[name])

            w = self.cols[name].get_widget()
            while not isinstance(w, Gtk.Button):
                w = w.get_parent()

            w.connect('button-press-event', self._header_button_press)

            if name not in self.visible_columns:
                self.cols[name].set_visible(False)

        #renderer_id = Gtk.CellRendererText()
        #self.cols['ID'].pack_start(renderer_id, False, True, 0)
        # self.cols['ID'].set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
        # self.cols['ID'].set_expand(False)
        #self.cols['ID'].add_attribute(renderer_id, 'text', 0)

        renderer_title = Gtk.CellRendererText()
        self.cols['Title'].pack_start(renderer_title, False)
        self.cols['Title'].set_resizable(True)
        self.cols['Title'].set_sizing(Gtk.TreeViewColumnSizing.FIXED)
        self.cols['Title'].set_expand(True)
        self.cols['Title'].add_attribute(renderer_title, 'text', 1)
        # Using foreground-gdk does not work, possibly due to the timing of it being set
        self.cols['Title'].add_attribute(renderer_title, 'foreground', 9)
        renderer_title.set_property('ellipsize', Pango.EllipsizeMode.END)

        renderer_progress = Gtk.CellRendererText()
        self.cols['Progress'].pack_start(renderer_progress, False)
        self.cols['Progress'].add_attribute(renderer_progress, 'text', 4)
        self.cols['Progress'].set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
        self.cols['Progress'].set_expand(False)

        if self.progress_style == 0:
            renderer_percent = Gtk.CellRendererProgress()
            self.cols['Percent'].pack_start(renderer_percent, False)
            self.cols['Percent'].add_attribute(renderer_percent, 'value', 10)
        else:
            renderer_percent = ProgressCellRenderer(self.colors)
            self.cols['Percent'].pack_start(renderer_percent, False)
            self.cols['Percent'].add_attribute(renderer_percent, 'value', 2)
            self.cols['Percent'].add_attribute(renderer_percent, 'total', 6)
            self.cols['Percent'].add_attribute(renderer_percent, 'subvalue', 7)
            self.cols['Percent'].add_attribute(renderer_percent, 'eps', 8)
        renderer_percent.set_fixed_size(100, -1)

        renderer = Gtk.CellRendererText()
        self.cols['Score'].pack_start(renderer, False)
        self.cols['Score'].add_attribute(renderer, 'text', 5)
        renderer = Gtk.CellRendererText()
        self.cols['Start'].pack_start(renderer, False)
        self.cols['Start'].add_attribute(renderer, 'text', 11)
        renderer = Gtk.CellRendererText()
        self.cols['End'].pack_start(renderer, False)
        self.cols['End'].add_attribute(renderer, 'text', 12)
        renderer = Gtk.CellRendererText()
        self.cols['My start'].pack_start(renderer, False)
        self.cols['My start'].add_attribute(renderer, 'text', 13)
        renderer = Gtk.CellRendererText()
        self.cols['My end'].pack_start(renderer, False)
        self.cols['My end'].add_attribute(renderer, 'text', 14)

    def _header_button_press(self, button, event):
        if event.button == 3:
            menu = Gtk.Menu()
            for name, sort in self.available_columns:
                is_active = name in self.visible_columns

                item = Gtk.CheckMenuItem(name)
                item.set_active(is_active)
                item.connect('activate', self._header_menu_item,
                             name, not is_active)
                menu.append(item)
                item.show()

            menu.popup_at_pointer(event)
            return True

        return False

    @property
    def filter(self):
        return self.props.model.props.model

    def show_tooltip(self, view, x, y, kbd, tip):
        has_path, tx, ty, model, path, _iter = view.get_tooltip_context(
            x, y, kbd)
        if has_path:
            _, col, _, _ = view.get_path_at_pos(tx, ty)
            renderer = next(k for i, k in enumerate(col.get_cells()) if i == 0)
            lines = []

            if col == self.cols['Percent']:
                lines.append("Watched: %d" %
                             view.filter.get_value(path, 'stat'))
                if view.filter.get_value(path, 'subvalue') and not view.filter.get_value(path, 'status') == utils.STATUS_NOTYET:
                    lines.append("Aired%s: %d" % (' (estimated)' if view.filter.get_value(
                        path, 'status') == utils.STATUS_AIRING else '', view.filter.get_value(path, 'subvalue')))

                if len(view.filter.get_value(path, 'avail-eps')) > 0:
                    lines.append("Available: %d" %
                                 max(view.filter.get_value(path, 'avail-eps')))

                lines.append("Total: %s" %
                             (view.filter.get_value(path, 'total-eps') or '?'))

            if len(lines):
                tip.set_markup('\n'.join(lines))
                self.set_tooltip_cell(tip, path, col, renderer)
                return True
        return False

    def _header_menu_item(self, w, column_name, visible):
        self.emit('column-toggled', column_name, visible)

    def select(self, show):
        """Select specified row or first if not found"""
        for row in self.get_model():
            if int(row[0]) == show['id']:
                selection = self.get_selection()
                selection.select_iter(row.iter)
                return

        self.get_selection().select_path(Gtk.TreePath.new_first())


class ProgressCellRenderer(Gtk.CellRenderer):
    value = 0
    subvalue = 0
    _total = 0
    eps = []
    _subheight = 5

    __gproperties__ = {
        "value": (GObject.TYPE_INT, "Value",
                  "Progress percentage", 0, 100000, 0,
                  GObject.ParamFlags.READWRITE),

        "subvalue": (GObject.TYPE_INT, "Subvalue",
                     "Sub percentage", 0, 100000, 0,
                     GObject.ParamFlags.READWRITE),

        "total": (GObject.TYPE_INT, "Total",
                  "Total percentage", 0, 100000, 0,
                  GObject.ParamFlags.READWRITE),

        "eps": (GObject.TYPE_PYOBJECT, "Episodes",
                "Available episodes",
                GObject.ParamFlags.READWRITE),
    }

    def __init__(self, colors):
        Gtk.CellRenderer.__init__(self)
        self.colors = colors
        self.value = self.get_property("value")
        self.subvalue = self.get_property("subvalue")
        self.total = self.get_property("total")
        self.eps = self.get_property("eps")

    def do_set_property(self, pspec, value):
        setattr(self, pspec.name, value)

    @property
    def total(self):
        return self._total if self._total > 0 else len(self.eps)

    @total.setter
    def total(self, value):
        self._total = value

    def do_get_property(self, pspec):
        return getattr(self, pspec.name)

    def do_render(self, cr, widget, background_area, cell_area, flags):
        (x, y, w, h) = self.do_get_size(widget, cell_area)

        # set_source_rgb(0.9, 0.9, 0.9)
        cr.set_source_rgb(*self.__get_color(self.colors['progress_bg']))
        cr.rectangle(x, y, w, h)
        cr.fill()

        if not self.total:
            return

        if self.subvalue:
            if self.subvalue > self.total:
                mid = w
            else:
                mid = int(w / float(self.total) * self.subvalue)

            # set_source_rgb(0.7, 0.7, 0.7)
            cr.set_source_rgb(
                *self.__get_color(self.colors['progress_sub_bg']))
            cr.rectangle(x, y+h-self._subheight, mid, h-(h-self._subheight))
            cr.fill()

        if self.value:
            if self.value >= self.total:
                # set_source_rgb(0.6, 0.8, 0.7)
                cr.set_source_rgb(
                    *self.__get_color(self.colors['progress_complete']))
                cr.rectangle(x, y, w, h)
            else:
                mid = int(w / float(self.total) * self.value)
                # set_source_rgb(0.6, 0.7, 0.8)
                cr.set_source_rgb(
                    *self.__get_color(self.colors['progress_fg']))
                cr.rectangle(x, y, mid, h)
            cr.fill()

        if self.eps:
            # set_source_rgb(0.4, 0.5, 0.6)
            cr.set_source_rgb(
                *self.__get_color(self.colors['progress_sub_fg']))
            for episode in self.eps:
                if episode > 0 and episode <= self.total:
                    start = int(w / float(self.total) * (episode - 1))
                    finish = int(w / float(self.total) * episode)
                    cr.rectangle(x+start, y+h-self._subheight,
                                 finish-start, h-(h-self._subheight))
                    cr.fill()

    @staticmethod
    def do_get_size(widget, cell_area):
        if cell_area is None:
            return 0, 0, 0, 0
        x = cell_area.x
        y = cell_area.y
        w = cell_area.width
        h = cell_area.height
        return x, y, w, h

    @staticmethod
    def __get_color(color_string):
        color = Gdk.color_parse(color_string)
        return color.red_float, color.green_float, color.blue_float
