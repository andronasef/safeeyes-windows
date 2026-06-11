#!/usr/bin/python3


import io
from pathlib import Path
from setuptools import Command, setup
from setuptools.command.build import build as OriginalBuildCommand

# Many of the project's .po files (synced from Weblate) carry an empty
# "POT-Creation-Date:" header. Babel's strict parser rejects an empty date,
# while the gettext `msgfmt` tool ignored it. Give such headers a placeholder
# date so compilation matches the old lenient behaviour. The "\n" below is the
# literal two-character PO line-continuation escape, so only genuinely empty
# headers match.
_EMPTY_DATE_HEADERS = (
    (b'"POT-Creation-Date: \\n"', b'"POT-Creation-Date: 2000-01-01 00:00+0000\\n"'),
    (b'"PO-Revision-Date: \\n"', b'"PO-Revision-Date: 2000-01-01 00:00+0000\\n"'),
)


def compile_po(source_file, build_file):
    """Compile a single .po file into a .mo file using Babel."""
    from babel.messages.mofile import write_mo
    from babel.messages.pofile import read_po

    data = Path(source_file).read_bytes()
    for empty, placeholder in _EMPTY_DATE_HEADERS:
        data = data.replace(empty, placeholder)

    catalog = read_po(io.BytesIO(data))
    with open(build_file, "wb") as mo:
        write_mo(mo, catalog)


class BuildCommand(OriginalBuildCommand):
    sub_commands = [("build_mo", None), *OriginalBuildCommand.sub_commands]


class BuildMoSubCommand(Command):
    description = "Compile .po files into .mo files"

    files = None

    def initialize_options(self):
        self.files = None
        self.editable_mode = False
        self.build_lib = None

    def finalize_options(self):
        self.set_undefined_options("build_py", ("build_lib", "build_lib"))

    def run(self):
        # Use Babel to compile .po -> .mo instead of spawning the gettext
        # `msgfmt` binary, which is not available on Windows.
        files = self._get_files()

        for build_file, source_file in files.items():
            if not self.editable_mode:
                Path(build_file).parent.mkdir(parents=True, exist_ok=True)
            compile_po(source_file, build_file)

    def _get_files(self):
        if self.files is not None:
            return self.files

        files = {}

        localedir = Path("safeeyes/config/locale")
        po_dirs = [d.joinpath("LC_MESSAGES") for d in localedir.iterdir() if d.is_dir()]
        for po_dir in po_dirs:
            po_files = [
                f for f in po_dir.iterdir() if f.is_file() and f.suffix == ".po"
            ]
            for po_file in po_files:
                mo_file = po_file.with_suffix(".mo")

                source_file = po_file
                build_file = mo_file

                if not self.editable_mode:
                    build_file = Path(self.build_lib).joinpath(build_file)

                files[str(build_file)] = str(source_file)

        self.files = files
        return files

    def get_output_mapping(self):
        return self._get_files()

    def get_outputs(self):
        return self._get_files().keys()

    def get_source_files(self):
        return self._get_files().values()


setup(cmdclass={"build": BuildCommand, "build_mo": BuildMoSubCommand})
