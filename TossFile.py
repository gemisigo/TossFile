from string import Template
import os
import re
import shutil
import sublime
import sublime_plugin
import inspect
from TossFile.pyads.pyads import ADS

SETTINGS = [
    "merge_global_paths",
    "merge_global_source_path_excludes",
    "merge_global_name_excludes",
    "merge_global_extension_excludes",
    "paths",
    "destination_path_excludes",
    "extension_excludes",
    "name_excludes",
    "replace_if_exists",
    "source_path_excludes",
    "status_timeout",
]

ACTIONS = {
    "create table": "new",
    "alter table": "mod",
    "alter procedure": "mod",
    "usp_add_fk": "mod",
    "usp_add_column": "mod",
    "usp_add_constraint": "mod",
    "usp_drop_fk": "mod",
    "usp_drop_column": "mod",
    "usp_drop_constraint": "mod",
    "create view": "view",
    "create or replace view": "view",
    "create procedure": "usp",
    "create or replace procedure": "usp",
    "create function": "udf",
    "create or replace function": "udf",
    "create schema": "schema",
    "create or replace schema": "schema",
    "insert": "ibd",
    "insert into": "ibd",
    "insert ignore into": "ibd",
    "tt_ibd": "ibd"
}

action_pipe = "|".join(ACTIONS.keys()).lower()
OPENING_DELIMITERS = "`'\"\\["
CLOSING_DELIMITERS = "`'\"\\]"
od = OPENING_DELIMITERS
cd = CLOSING_DELIMITERS
USE_PATTERN = f"(?i)(?:use\\s*[{od}]?(?P<schema1>\\w*)[{cd}]?;?)"
# ACTION_PATTERN = f"[{od}]?(?P<action>{action_pipe})[{cd}]?\\s*(\\(\\s*')?(?:[{od}](?P<schema2>\\w*)[{cd}]\\.[{od}](?P<object1>\\w*)[{cd}]|[{od}](?P<object2>\\w*)[{cd}])"
# ACTION_PATTERN = f"(?i)[{od}]?(?P<action>(${action_pipe}))[{cd}]?\\s+(?:[{od}](?P<schema>.*?)[{cd}]\\.)?(?:[{od}](?P<object>.*?)[{cd}])"
# ACTION_PATTERN = f"(?i)[{od}]?(?P<action>(${action_pipe}))[{cd}]?(?:\s+LIKE)\s+(?:[{od}](?P<schema>.*?)[{cd}]\.)?(?:[{od}](?P<object>.*?)[{cd}])"
# ACTION_PATTERN = f"(?i)[{od}]?(?P<action>(${action_pipe}))[{cd}]?\s+(?:(IF NOT EXISTS|LIKE)\s+)?(?:[{od}]?(?P<schema>[^{cd}]*)[{cd}]?\.)?(?:[{od}]?(?P<object>[^{cd}]*[{cd}]?))"
ACTION_PATTERN = f"(?i)[{od}]?(?P<action>(${action_pipe}))[{cd}]?\s+(?:(IF NOT EXISTS|LIKE)\s+)?(?:[{od}]?(?P<schema>[^{cd}]*)[{cd}]?\.)?(?:[{od}]?(?P<object>[^{cd}]+)[{cd}]?)"



def coalesce(*values):
    """Return the first non-None value or None if all values are None"""
    return next((v for v in values if v is not None), None)

def get_settings(view):
    # print("TossFile: load settings")
    plugin_name = "TossFile"
    mgp = "merge_global_"
    global_settings = sublime.load_settings("%s.sublime-settings" % plugin_name)
    project_settings = view.settings().get(plugin_name, {})
    combined_settings = {}

    for setting in SETTINGS:
        combined_settings[setting] = global_settings.get(setting)

    # print(f"project settings: {project_settings}")
    for key in project_settings:
        # print(f"project key: {key}")
        if key in SETTINGS:
            if mgp+key in project_settings and project_settings[mgp + key]:
                combined_settings[key] = global_settings[key] + project_settings[key]
            else:
                combined_settings[key] = project_settings[key]
        else:
            print(f"TossFile: Invalid key [{key}] in project settings.")
    return combined_settings


class BaseTossFile(sublime_plugin.TextCommand):

    debug_level = 10

    def printd(self, text: str, debug_level: int = 20, end: str = "\n"):
        """Print debug"""
        if self.debug_level <= debug_level:
            caller = inspect.stack()[1][3]  # will give the caller of foos name, if something called foo
            dname = f"{self.__class__.__name__}.{caller} [{debug_level}]"
            print(f"{dname}: {text}", end = end)

    def init_toss(self, toss_type):
        self.toss_file_type = toss_type
        self.num_files_tossed = 0
        self.num_locations_tossed = 0
        self.num_files_skipped = 0
        self.num_locations_skipped = 0
        self.num_files_abandoned = 0
        self.debug = True
        combined_settings = get_settings(self.view)
        self.printd(f"{combined_settings=}")

    def prepared_file_name(self, file_name):
        if not file_name:
            try:
                buffer_content = self.view.substr(sublime.Region(0, self.view.size()))[0:1000].lower()
                selections = self.view.sel()
                use_pattern = re.compile(USE_PATTERN)
                action_pattern = re.compile(ACTION_PATTERN)

                self.printd(f"{USE_PATTERN=}")
                self.printd(f"{ACTION_PATTERN=}")

                use_match = use_pattern.search(buffer_content[0:1000])
                self.printd(f"{use_match=}")
                schema_name = use_match.group("schema1")
                self.printd(f"{schema_name=}")

                action_match = action_pattern.search(buffer_content)
                self.printd(f"{action_match=}")
                action = action_match.group("action")
                self.printd(f"{action=}")
                # schema2 = action_match.group("schema2")
                # self.printd(f"{schema2=}")
                # object1 = action_match.group("object1")
                # self.printd(f"{object1=}")
                # object2 = action_match.group("object2")
                # self.printd(f"{object2=}")

                # schema_name = action_match.group("schema")
                # self.printd(f"{schema_name=}")
                object_name = action_match.group("object")
                self.printd(f"{object_name=}")

                # schema_name = coalesce(schema2, schema1)
                # object_name = coalesce(object2, object1)

                self.printd(f"{action=}")

                new_file_name = f"{ACTIONS[action.lower()]}.{schema_name}.{object_name}.sql"
                self.printd(f"{new_file_name=}")

                return (None, new_file_name) # (file_path, file_name)

            except IndexError as e:
                self.num_files_abandoned = self.num_files_abandoned + 1
                self.printd("IndexError")
                return None
        else:
            # return {"file_path": os.path.split(file_name)[0], "file_name": os.path.split(file_name)[1]}
            return (os.path.split(file_name)[0], os.path.split(file_name)[1]) # (file_path, file_name)

    def get_status_timeout(self):
        combined_settings = get_settings(self.view)
        timeout = combined_settings.get("status_timeout", 0)
        if not isinstance(timeout, int) or timeout == 0:
            timeout = 5
        timeout = timeout * 1000
        return timeout

    def get_status_str(self):
        toss_file_str = "file" if self.num_files_tossed == 1 else "files"
        toss_location_str = "location" if self.num_locations_tossed == 1 else "locations"
        skip_file_str = "file" if self.num_files_skipped == 1 else "files"
        skip_location_str = "location" if self.num_locations_skipped == 1 else "locations"
        tmpl = "$toss_file_type: tossed $num_files_tossed $toss_file_str to $num_locations_tossed $toss_location_str"
        if self.num_files_skipped > 0 or self.num_files_abandoned > 0:
            tmpl = tmpl + "; settings made toss skip $num_files_skipped $skip_file_str at $num_locations_skipped $skip_location_str, abandoned: $num_files_abandoned"
        status_template_str = Template(tmpl)
        return status_template_str.substitute(toss_file_type=self.toss_file_type,
                                              num_files_tossed=str(self.num_files_tossed),
                                              toss_file_str=toss_file_str,
                                              num_locations_tossed=str(self.num_locations_tossed),
                                              toss_location_str=toss_location_str,
                                              num_files_skipped=str(self.num_files_skipped),
                                              skip_file_str=skip_file_str,
                                              num_locations_skipped=str(self.num_locations_skipped),
                                              skip_location_str=skip_location_str,
                                              num_files_abandoned=str(self.num_files_abandoned)
                                              )

    def update_status(self):
        self.view.set_status("toss_file_status", self.get_status_str())
        sublime.set_timeout(lambda: self.clear_status(), self.get_status_timeout())

    def clear_status(self):
        self.view.set_status("toss_file_status", "")

    def skip(self, copy_from, copy_to, replace_if_exists):
        return self.skip_existing_file(copy_to, replace_if_exists) or self.skip_name(copy_to) or self.skip_extension(copy_to) or self.skip_path("destination_path_excludes", copy_to) or self.skip_path("source_path_excludes", copy_from)

    def skip_existing_file(self, copy_to, replace_if_exists):
        skip = False
        combined_settings = get_settings(self.view)
        if os.path.isfile(copy_to) and not replace_if_exists:
            skip = True
        return skip

    def skip_name(self, copy_to):
        skip = False
        combined_settings = get_settings(self.view)
        name_excludes = combined_settings.get("name_excludes", [])
        file_name = os.path.basename(copy_to)
        for name in name_excludes:
            if file_name == name:
                skip = True
                break
        return skip

    def skip_extension(self, copy_to):
        skip = False
        combined_settings = get_settings(self.view)
        extension_excludes = combined_settings.get("extension_excludes", [])
        file_extension = os.path.splitext(copy_to)[1]
        if file_extension:
            for extension in extension_excludes:
                if file_extension == extension:
                    skip = True
                    break
        return skip

    def skip_path(self, settingKey, target):
        skip = False
        combined_settings = get_settings(self.view)
        paths = combined_settings.get(settingKey, [])
        for path in paths:
            if target.startswith(path):
                skip = True
                break
        return skip


    def prepared_path(self, path, global_replace_if_exists):
        flat = path.get("flat", False)
        source = path.get("source")
        source = os.path.normpath(source) if source else None
        destination = os.path.normpath(path["destination"])
        if source and not os.path.isabs(source):
            project_path = self.view.window().extract_variables()["project_path"]
            source = os.path.join(project_path, source)
        if not os.path.isabs(destination):
            project_path = self.view.window().extract_variables()["project_path"]
            destination = os.path.join(project_path, destination)
        replace_if_exists = path.get("replace_if_exists", global_replace_if_exists)
        flat = path.get("flat", True if not source else False )
        # return {"source": source, "destination": destination, "replace_if_exists": replace_if_exists, "flat": flat}
        return (source, destination, replace_if_exists, flat)


    def toss(self, file_name, debug = False):
        is_file_tossed = False
        is_file_skipped = False
        combined_settings = get_settings(self.view)
        global_replace_if_exists = combined_settings.get("replace_if_exists", False)
        self.printd(f"{file_name=}")
        if debug:
            return "DOA"

        self.printd(f"{file_name=}")
        file_path, new_file_name = self.prepared_file_name(file_name)
        all_paths = combined_settings.get("paths", [])

        # it is saved already, fetch paths with source only
        if file_path:
            paths = (self.prepared_path(p, global_replace_if_exists) for p in all_paths if p.get("source") is not None)
        # is unsaved, fetch source-less paths only
        else:
            paths = (self.prepared_path(p, global_replace_if_exists) for p in all_paths if p.get("source") is None)

        paths = list(paths)
        self.printd(f"{paths=}")
        for source, destination, replace_if_exists, flat in paths:
            if not source:
                self.view.settings().set("default_dir", destination)
                self.view.set_name(new_file_name)
                self.view.assign_syntax("Packages/User/Gem-SQL.sublime-syntax")
                self.view.run_command("save")
                new_file_path = os.path.join(destination, new_file_name)
                # self.view.retarget(new_file_path)
            else:
                if file_path.startswith(source):
                    if flat:
                        copy_to = os.path.join(destination, new_file_name)
                    else:
                        copy_to = file_name.replace(source, destination)

                    if self.skip(file_name, copy_to, replace_if_exists):
                        self.num_locations_skipped = self.num_locations_skipped + 1
                        if not is_file_skipped:
                            self.num_files_skipped = self.num_files_skipped + 1
                            is_file_skipped = True
                    else:
                        copy_to_dir = os.path.dirname(copy_to)
                        if not os.path.exists(copy_to_dir):
                            os.makedirs(copy_to_dir)
                        shutil.copyfile(file_name, copy_to)
                        self.num_locations_tossed = self.num_locations_tossed + 1
                        if not is_file_tossed:
                            self.num_files_tossed = self.num_files_tossed + 1
                            is_file_tossed = True

class TossExternalFileCommand(BaseTossFile):
    def run(self, edit, file_name, **kwargs):
        self.init_toss("")

class TossFileCommand(BaseTossFile):
    def run(self, edit, **kwargs):
        self.init_toss("Toss File")
        self.toss(self.view.file_name())
        self.update_status()


class TossAllFilesCommand(BaseTossFile):
    def run(self, edit, **kwargs):
        self.init_toss("Toss All Files")
        open_views = self.view.window().views()
        for x in open_views:
            if x.name() != "TodoReview":
                self.toss(x.file_name(), True)
        self.update_status()
