import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

import rlbot.setup_manager
from rlbot.utils.structures.game_interface import get_dll_directory


class ACFFile(dict):
    """
    This class represents the .acf file format used by Steam.

    @param path: Path to the .acf file to parse
    """
    _OBJECT_NAME_RE = re.compile(r'^\t*"(.+)"$', re.MULTILINE)
    _OBJECT_BEGIN_RE = re.compile(r'^\t*{$', re.MULTILINE)
    _OBJECT_FINISH_RE = re.compile(r'^\t*}$', re.MULTILINE)
    _KEY_VALUE_RE = re.compile(r'^\t*"(.+)"\t+"(.*)"$', re.MULTILINE)

    def __init__(self, path):
        super().__init__()
        with open(path, 'r') as fp:
            self.parse(fp)

    def parse(self, fp):
        """
        Parse an .acf file

        @param fp: an iterable over lines in the acf file
        """
        self.update(self._parse(fp))

    def _parse(self, fp):
        retval = dict()
        for line in fp:
            match = self._OBJECT_BEGIN_RE.match(line)
            if match is not None:
                continue

            match = self._KEY_VALUE_RE.match(line)
            if match is not None:
                key, value = match.group(1, 2)
                retval[key] = value
            else:
                match = self._OBJECT_NAME_RE.match(line)
                if match is not None:
                    key = match.group(1)
                    retval[key] = self._parse(fp)

            match = self._OBJECT_FINISH_RE.match(line)
            if match is not None:
                break

        return retval


class ProtonHack:
    """
    Runs the given command in the same Proton prefix as Rocket League
    """
    _library_base_dir: Path
    _proton_base_dir: Path
    _proton_bin: Path
    _acf: dict
    env: dict

    def __init__(self):
        game_id = rlbot.setup_manager.ROCKET_LEAGUE_PROCESS_INFO.GAMEID
        self._acf = dict()

        steam_path_tmp = Path.home().joinpath('.steam/steam/steamapps/')

        libraryfolders = ACFFile(steam_path_tmp.joinpath('libraryfolders.vdf'))
        appmanifest = ACFFile(steam_path_tmp.joinpath(f'appmanifest_{game_id}.acf'))

        self._acf.update(libraryfolders)
        self._acf['appmanifest'] = appmanifest

        self._library_base_dir = self._locate_library_folder()
        self._compat_data = self._library_base_dir.joinpath(f'steamapps/compatdata/{game_id}/')
        self._proton_base_dir = self._find_proton_dir()
        self._proton_bin = self._proton_base_dir.joinpath('proton')
        self.env = self._prepare_env()

    def compat_data_exists(self):
        return self._compat_data.exists()

    def run_in_proton_prefix(self, command, env=None, cwd=None):
        args = self.prefix_proton_cmd(command)
        if env is None:
            env = dict(os.environ).update(self.env)

        subprocess.run(args, env=env, cwd=cwd, stdout=sys.stdout, stderr=sys.stderr, stdin=sys.stdin)

    def prefix_proton_cmd(self, command):
        cmd = [str(self._proton_bin), "runinprefix"] + command
        return cmd

    def _find_proton_dir(self):
        version_file = self._compat_data.joinpath("version")
        if version_file.exists():
            with open(version_file, "r") as f:
                version = f.readline().strip()
        else:
            return None

        proton_version, _ = version.split('-')
        proton_dir = f"Proton {proton_version}"

        for k, v in self._acf['libraryfolders'].items():
            if not isinstance(v, dict):
                continue
            if 'apps' not in v.keys():
                continue
            path = Path(v['path']).joinpath(f'steamapps/common/{proton_dir}/')
            if path.exists():
                return path

    def _locate_library_folder(self):
        found = False
        for k, v in self._acf['libraryfolders'].items():
            if not isinstance(v, dict):
                continue
            if 'apps' not in v.keys():
                continue
            if not str(rlbot.setup_manager.ROCKET_LEAGUE_PROCESS_INFO.GAMEID) in v['apps'].keys():
                continue
            for game_id in v['apps'].keys():
                if game_id == str(rlbot.setup_manager.ROCKET_LEAGUE_PROCESS_INFO.GAMEID):
                    found = True
                    break
            if found:
                break

        if not found:
            return None

        return Path(self._acf['libraryfolders'][k]['path'])

    def _prepare_env(self):
        env = dict()
        env['STEAM_COMPAT_DATA_PATH'] = str(self._compat_data)
        return env


def main():
    from rlbot.gateway_util import IDEAL_RLBOT_PORT

    ph = ProtonHack()
    cmd = ph.prefix_proton_cmd([os.path.join(get_dll_directory(), 'RLBot.exe'), str(IDEAL_RLBOT_PORT)])
    cmd = [shlex.quote(x) for x in cmd]
    print(str(cmd))


if __name__ == '__main__':
    main()
