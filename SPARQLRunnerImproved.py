try:
    from urllib.parse import urlencode
except ImportError:
    from urllib import urlencode

try:
    from urllib.request import urlopen, Request
except ImportError:
    from urllib2 import urlopen, Request

from json import loads
import threading
import re
import base64

import sublime
import sublime_plugin


PROGRESS = ['-', '\\', '|', '/']
PREFIX_REGEX = re.compile(r'^\s*prefix\s+(.*?)\s+<(.*?)>\s*$', re.MULTILINE | re.IGNORECASE)
SETTINGS_FILE = 'SPARQLRunnerImproved.sublime-settings'

def get_endpoint_name(name, endpoints):
    """ Returns endpoint name if exists (case-insensitive) """
    for k in endpoints:
        if k.lower() == name.lower():
            return k
    return None

class QueryRunner(threading.Thread):
    def __init__(self, server, query, prefixes, auth=None):
        self.server = server
        self.query = query
        self.result = None
        self.prefixes = prefixes
        super(QueryRunner, self).__init__()

    def parse_prefixes(self):
        return self.prefixes + PREFIX_REGEX.findall(self.query)

    def replace_prefix(self, value, prefixes):
        for prefix, url in prefixes:
            if value.find(url) == 0:
                return value.replace(url, prefix)
        return value

    def format_result(self, result):
        prefixes = self.parse_prefixes()
        bindings = result['results']['bindings']
        variables = result['head']['vars']
        number_of_variables = len(variables)
        max_column_size = [len(varname) for varname in variables]
        column_padding = 2

        for line in bindings:
            for i, varname in enumerate(variables):
                variable_entry = line.get(varname, {})
                variable_value = variable_entry.get('value', '')
                variable_entry['value'] = variable_value = self.replace_prefix(variable_value, prefixes)
                line[varname] = variable_entry
                if len(variable_value) > max_column_size[i]:
                    max_column_size[i] = len(variable_value)

        output = []
        for i, varname in enumerate(variables):
            output.append(varname + " " * (max_column_size[i] - len(varname)))
            if i < number_of_variables - 1:
                output.append(" " * column_padding)
        output.append("\n")

        for i, varname in enumerate(variables):
            output.append("-" * max_column_size[i])
            if i < number_of_variables - 1:
                output.append(" " * column_padding)
        output.append("\n\n")

        for line in bindings:
            for i, varname in enumerate(variables):
                value = line[varname]['value'].replace('\n', '\\n').replace('\r', '\\r')
                output.append(value + " " * (max_column_size[i] - len(value)))
                if i < number_of_variables - 1:
                    output.append(" " * column_padding)
            output.append("\n")

        return "".join(output)

    def run(self):
        try:
            params = dict({
                    'query': self.query
                },
                **self.server.get("parameters", {})
            )

            url = self.server['url'] + '?' + urlencode(params)
            req = Request(url)
            if self.server.get('username', "") > "":
                up = "%s:%s" % (self.server['username'], self.server['password'])
                enc = base64.standard_b64encode(up.encode("utf-8"))
                req.add_header("Authorization", "Basic %s" % enc.decode("utf-8"))

            # run query and parse headers
            res = urlopen(req)
            headers = dict(res.getheaders())
            ctype = headers.get('Content-Type', "").split(';')[0]

            # check length
            if headers.get('Content-Length', -1) == 0:
                raise Exception("No content in response")
            self.result = res.read().decode("utf-8")

            # parse based on content type
            if ctype == "text/plain":
                pass
            elif ctype == "application/json":
                self.result = self.format_result(res.read())
            else:
                raise Exception("Response content type not supported: %s" % ctype)
        except Exception as e:
            err = '%s: Error %s running query' % (__name__, str(e))
            sublime.error_message(err)


class RunSparqlCommand(sublime_plugin.TextCommand):
    def get_selection(self):
        sels = self.view.sel()
        if len(sels) == 0:
            return None
        first_selection = self.view.substr(sels[0])
        if len(first_selection) == 0:
            return None

        return first_selection

    def get_full_text(self):
        return self.view.substr(sublime.Region(0, self.view.size()))

    def handle_thread(self, thread, i=0):
        if thread.is_alive():
            self.view.set_status('sparql_query', 'Running your query on %s [%s]' % (thread.server, PROGRESS[i]))
            sublime.set_timeout(lambda: self.handle_thread(thread, (i + 1) % len(PROGRESS)), 100)
            return

        self.view.erase_status('sparql_query')

        if not thread.result:
            return

        sublime.status_message('Query successfully run on %s' % thread.server)
        new_view = self.view.window().new_file()
        new_view.settings().set('word_wrap', False)
        new_view.set_name("SPARQL Query Results")
        try:
            # Sublime Text 2 way
            edit = new_view.begin_edit()
            new_view.insert(edit, 0, thread.result)
            new_view.end_edit(edit)
        except:
            new_view.run_command('append', {
                'characters': thread.result
            })
        new_view.run_command("goto_line", {"line": 1})
        new_view.set_scratch(True)
        new_view.set_read_only(True)

    def run(self, edit):
        self.settings = sublime.load_settings(SETTINGS_FILE)
        self.endpoints = self.settings.get("endpoints", None)
        name = self.settings.get('current', None)
        if not name or not self.endpoints or not get_endpoint_name(name, self.endpoints):
            sublime.error_message("You should add/select an endpoint using 'SPARQL: Select endpoint' command.")
            return

        query = self.get_selection() or self.get_full_text()
        query_thread = QueryRunner(self.endpoints[name], query, self.settings.get('prefixes', []))
        query_thread.start()
        self.handle_thread(query_thread)


class SelectSparqlEndpointCommand(sublime_plugin.WindowCommand):
    def run(self):
        # editing existing
        self.editing = False
        self.old_parameters = []
        self.old_parameter_index = 0
        # general
        self.parameters = {}
        self.settings = sublime.load_settings(SETTINGS_FILE)
        self.current = self.settings.get('current', None)
        self.endpoints = self.settings.get('endpoints', {})
        self.list_endpoints()
        # show listing
        self.window.show_quick_panel(self.listing, self.on_panel_select_done)

    def list_endpoints(self):
        self.listing = [
            ['Add new or edit existing endpoint...', ''],
        ]

        for name, props in self.endpoints.items():
            title = "*%s" % name if name == self.current else name
            self.listing.append([title, name, props['url'], props.get('username', "")])

    def finalise_endpoint(self):
        # prepare data
        data = {'url': self.url}
        if self.username and self.password:
            data = dict({'username': self.username, 'password': self.password}, **data)
        if len(self.parameters):
            data['parameters'] = self.parameters
        # add data
        self.settings.set('endpoints', dict(self.endpoints, **{self.name: data}))
        self.set_as_current(self.name)

    def add_parameter(self, name, value):
        self.parameters[name] = value

    def set_as_current(self, name):
        self.settings.set('current', name)
        sublime.save_settings(SETTINGS_FILE)

    def get_prop(self, name, prop):
        return self.endpoints[name].get(prop, "") if self.editing else ""

    def on_panel_select_done(self, selected):
        if selected < 0:
            return

        if selected == 0:
            self.window.show_input_panel('Endpoint name', '', self.on_name_done, self.on_change, self.on_cancel)
            return
        self.set_as_current(self.listing[selected][1])

    def on_name_done(self, name):
        self.name = name
        existing = get_endpoint_name(name, self.endpoints)
        if existing:
            self.editing = sublime.ok_cancel_dialog("Current name '%s' already in use for endpoint. Do you want to edit it?" % existing)
            if not self.editing:
                return
            self.name = existing
            self.old_parameters = [(k, v) for k,v in self.get_prop(self.name, "parameters").items()]
        self.window.show_input_panel('Endpoint URL', self.get_prop(self.name, "url"), self.on_url_done, self.on_change, self.on_cancel)

    def on_url_done(self, url):
        self.url = url
        self.window.show_input_panel('Endpoint username (leave empty to skip)', self.get_prop(self.name, "username"), self.on_username_done, self.on_change, self.on_cancel)

    def on_username_done(self, username):
        self.username = username
        if self.username > "":
            self.window.show_input_panel('Endpoint password', self.get_prop(self.name, "password"), self.on_password_done, self.on_change, self.on_cancel)
        else:
            self.start_parameters()

    def on_password_done(self, password):
        self.password = password
        self.start_parameters()

    def get_current_parameter_prop(self, index):
        if len(self.old_parameters) > self.old_parameter_index:
            return self.old_parameters[self.old_parameter_index][index]
        else:
            return ""

    def start_parameters(self):
        self.window.show_input_panel('Parameter name (leave empty to skip)', self.get_current_parameter_prop(0), self.on_parameter_name_done, self.on_change, self.on_cancel)

    def on_parameter_name_done(self, name):
        if name > "":
            self.parameter_name = name
            self.window.show_input_panel('Parameter value', self.get_current_parameter_prop(1), self.on_parameter_value_done, self.on_change, self.on_cancel)
        else:
            self.finalise_endpoint()

    def on_parameter_value_done(self, value=""):
        if value > "":
            self.add_parameter(self.parameter_name, value)
            self.old_parameter_index += 1
            self.start_parameters()

    def on_change(self, name):
        pass

    def on_cancel(self):
        pass
