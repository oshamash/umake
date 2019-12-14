import sys
import threading
import os
from os.path import join
from subprocess import check_output, CalledProcessError
from datetime import datetime

ROOT = os.getcwd()
UMAKE_ROOT_DIR = join(ROOT, ".umake")
UMKAE_TMP_DIR = join(UMAKE_ROOT_DIR, "tmp")
UMAKE_DB = join(UMAKE_ROOT_DIR, "db.pickle")
UMAKE_BUILD_CACHE_DIR = join(UMAKE_ROOT_DIR, "build-cache")
UMAKE_BUILD_CACHE_MAX_SIZE_MB = 1500
MINIMAL_ENV = {"PATH": "/usr/bin"}
UMAKE_MAX_WORKERS = 4


file_action_fmt = "   [{action}] {filename}"
is_ineractive_terminal = sys.stdout.isatty()

def get_size_KB(path):
    try:
        return int(check_output(['du','-s', path]).split()[0].decode('utf-8'))
    except CalledProcessError:
        return 0


class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class AtomicInt:
    def __init__(self):
        self.num = 0
        self.lock = threading.Lock()
    
    def inc(self):
        with self.lock:
            self.num += 1
    
    def dec(self):
        with self.lock:
            self.num -= 1
    
    def __repr__(self):
        return str(self.num)

class InteractiveOutput:
    
    def __init__(self):
        self.bar_lock = threading.Lock()
        self.n_active_workers = AtomicInt()
        self.n_cache_hits = 0
        self.n_works_done = 0
        self.cache_current = "N/A"
        self.start_time = datetime.now()
        self.curr_job = ""

        self.n_calls = 0

    def _get_curr_cache_size(self):
        if self.n_calls % 10:
            return self.cache_current

        curr_size_mb = get_size_KB(UMAKE_BUILD_CACHE_DIR) / 1024
        self.cache_current = curr_size_mb

    def update_bar(self, force=False):
        with self.bar_lock:
            if force:
                self.n_calls = 0
            self._get_curr_cache_size()
            bright_blue = "\033[1;34;40m"
            bold = "\033[1;37;40m"
            diff = int((datetime.now() - self.start_time).total_seconds())
            
            sys.stdout.write("\x1b[2K\r")
            print(f"\r{bright_blue} Workers   {bcolors.ENDC}{bold} {self.n_active_workers}/{UMAKE_MAX_WORKERS}     {bcolors.ENDC}", end="")
            print(f"{bright_blue} Cache   {bcolors.ENDC}{bold} {int(self.cache_current)}/{UMAKE_BUILD_CACHE_MAX_SIZE_MB}[MB]   {bcolors.ENDC}", end="")
            if self.n_works_done:
                cache_ratio = int(self.n_cache_hits / self.n_works_done * 100)
                print(f"{bright_blue} Cache Hits   {bcolors.ENDC}{bold} {cache_ratio}%   {bcolors.ENDC}", end="")
            print(f"{bright_blue} Time   {bcolors.ENDC}{bold} {diff}[sec]   {bcolors.ENDC}", end="")
            print(f"{bold} {self.curr_job}   {bcolors.ENDC}", end="")
            sys.stdout.flush()
            
            self.n_calls += 1
    
    def print_colored(self, out_str, color=""):
        if is_ineractive_terminal:
            sys.stdout.write("\x1b[2K\r")
            print(f"{color} {out_str} {bcolors.ENDC}")
        else:
            print(f"{out_str}")
        # self.update_bar()

    def print_fail(self, out_str):
        self.print_colored(out_str, bcolors.FAIL)

    def print_neutarl(self, out_str):
        self.print_colored(out_str, bcolors.BOLD)

    def print_ok(self, out_str, color=bcolors.OKGREEN):
        self.print_colored(out_str, color)

    def print_file_deleted(self, filename, action="D"):
        self.print_fail(file_action_fmt.format(action=action, filename=filename))

    def print_file_add(self, filename):
        self.print_ok(file_action_fmt.format(action="A", filename=filename))

    def print_file_updated(self, filename):
        self.print_ok(file_action_fmt.format(action="U", filename=filename), bcolors.OKBLUE)

    def print(self, s):
        self.print_colored(s)

    def destroy(self):
        print()