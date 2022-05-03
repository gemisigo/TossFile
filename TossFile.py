from string import Template
import os
import shutil
import sublime
import sublime_plugin


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

def get_settings(view):
    # print("TossFile: load settings")
    plugin_name = "TossFile"
    mgp = "merge_global_"
    global_settings = sublime.load_settings("%s.sublime-settings" % plugin_name)
    # print(f"global settings: {global_settings}")
    project_settings = view.settings().get(plugin_name, {})
    # print(f"view: {view}")
    # print(f"view.settings: {view.settings}")
    # print(f"view.settings(): {view.settings()}")
    # print(view.settings().get(plugin_name, {}))
    # return {}
    # plugin_name = "Shit"
    # plugin_name = "TossFile"
    # shit = view.settings().get(plugin_name, {})
    # print(f"shit: {shit}, plugin_name: {plugin_name}")

    # print(f"dict(view.settings()): {dict(view.settings())}")
    # print(f"project settings: {project_settings}")
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
    def init_toss(self, toss_type):
        self.toss_file_type = toss_type
        self.num_files_tossed = 0
        self.num_locations_tossed = 0
        self.num_files_skipped = 0
        self.num_locations_skipped = 0
        self.debug = True
        combined_settings = get_settings(self.view)
        self.debug_print(f"TossFile: combined settings: {combined_settings}")
        # print(combined_settings["status_timeout"])

    def debug_print(self, stuff):
        if self.debug:
            print(f"TossFile debug: --[ {stuff} ]--")

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
        if self.num_files_skipped > 0:
            tmpl = tmpl + "; settings made toss skip $num_files_skipped $skip_file_str at $num_locations_skipped $skip_location_str"
        status_template_str = Template(tmpl)
        return status_template_str.substitute(toss_file_type=self.toss_file_type,
                                              num_files_tossed=str(self.num_files_tossed),
                                              toss_file_str=toss_file_str,
                                              num_locations_tossed=str(self.num_locations_tossed),
                                              toss_location_str=toss_location_str,
                                              num_files_skipped=str(self.num_files_skipped),
                                              skip_file_str=skip_file_str,
                                              num_locations_skipped=str(self.num_locations_skipped),
                                              skip_location_str=skip_location_str)

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
        # replace_if_exists = combined_settings.get("replace_if_exists", True)
        # if type(replace_if_exists) != bool:
            # replace_if_exists = True
        # if not replace_if_exists:
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

    def toss(self, file_name):
        is_file_tossed = False
        is_file_skipped = False
        combined_settings = get_settings(self.view)
        global_replace_if_exists = combined_settings.get("replace_if_exists", False)
        self.debug_print(f"file_name: {file_name}")
        if not file_name:
            for sel in self.view.sel():
                selected = self.view.substr(sel)
                self.debug_print(selected)

        else: # if file_name:
            paths = combined_settings.get("paths", [])
            # print(f"paths: {paths}")
            for path in paths:
                source = path.get("source")
                source = os.path.normpath(source) if source else None
                destination = os.path.normpath(path["destination"])
                replace_if_exists = path.get("replace_if_exists", global_replace_if_exists)
                flat = path.get("flat", True if not source else False )
                if source and file_name.startswith(source):
                    if flat:
                        copy_to = os.path.join(destination, os.path.split(file_name)[1])
                    else:
                        copy_to = file_name.replace(source, destination)
                # if file_name.startswith(source):
                #     copy_to = file_name.replace(source, destination)
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



class TossFileCommand(BaseTossFile):
    def run(self, edit, **kwargs):
        self.init_toss("Toss File")
        self.toss(self.view.file_name())
        self.update_status()


class TossAllFilesCommand(BaseTossFile):
    def run(self, edit, **kwargs):
        self.init_toss("Toss All Files")
        open_views = self.view.window().views()
        # for x in open_views:
            # self.toss(x.file_name())
        self.update_status()
