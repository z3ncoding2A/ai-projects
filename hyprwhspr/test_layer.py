import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gtk4LayerShell', '1.0')
from gi.repository import Gtk, Gtk4LayerShell, GLib

def on_activate(app):
    win = Gtk.ApplicationWindow(application=app)
    Gtk4LayerShell.init_for_window(win)
    print("Init successful.")
    win.present()
    GLib.timeout_add_seconds(1, app.quit)

app = Gtk.Application(application_id='com.example.test')
app.connect('activate', on_activate)
app.run(None)
