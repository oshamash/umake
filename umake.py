#!/usr/bin/python3.6
import time
from colored_output import InteractiveOutput, bcolors, ROOT, UMAKE_ROOT_DIR, UMKAE_TMP_DIR, UMAKE_DB, UMAKE_BUILD_CACHE_DIR, UMAKE_BUILD_CACHE_MAX_SIZE_MB, MINIMAL_ENV, get_size_KB, UMAKE_MAX_WORKERS

# from pyinstrument import Profiler
# profiler = Profiler()

out = InteractiveOutput()


class Config:
    def __init__(self):
        self.json_file = None
        self.interactive_output = False


global_config = Config()

class Timer:    
    def __init__(self, msg, threshold=0, color=bcolors.OKGREEN):
        self.msg = msg
        self.postfix = ""
        self.prefix = ""
        self.threshold = threshold
        self.color = color

    def set_prefix(self, prefix):
        self.prefix = prefix

    def set_postfix(self, postfix):
        self.postfix = postfix

    def __enter__(self):
        self.start = time.time()
        return self

    def __exit__(self, *args):
        self.end = time.time()
        self.interval = self.end - self.start
        if self.interval > self.threshold:
            out.print_colored(f"[{self.interval:.3f}] {self.prefix} {self.msg} {self.postfix}", self.color)


class MetadataCache:
    def __init__(self, deps):
        self.deps = deps

def fs_lock(path):
    lock_path = path + ".lock"
    try:
        fd = os.open(lock_path,  os.O_CREAT | os.O_EXCL)
        return fd, lock_path
    except FileExistsError:
        return None, None


def fs_unlock(fd, lock_path):
    try:
        os.close(fd)
    finally:
        os.remove(lock_path)


def open_cache(cache_hash) -> MetadataCache:
    cache_src = join(UMAKE_BUILD_CACHE_DIR, "md-" + cache_hash.hex())
    with open(cache_src, "rb") as metadata_file:
        metadata = pickle.load(metadata_file)
        return metadata


def save_cache(cache_hash, metadata_cache: MetadataCache):
    cache_src = join(UMAKE_BUILD_CACHE_DIR, "md-" + cache_hash.hex())
    with open(cache_src, "wb") as metadata_file:
        pickle.dump(metadata_cache, metadata_file, protocol=pickle.HIGHEST_PROTOCOL)


with Timer("done imports"):
    from subprocess import Popen, PIPE, check_output, TimeoutExpired
    from os.path import join
    from stat import S_ISDIR
    import os
    import uuid
    import shutil
    import hashlib
    from enum import Enum, auto
    import pickle
    import igraph
    import pprint
    import threading
    from queue import Queue, Empty
    from collections import OrderedDict
    from itertools import chain
    import shutil
    import sys
    import pywildcard as fnmatch


def byte_xor(ba1, ba2): 
    return bytes([_a ^ _b for _a, _b in zip(ba1, ba2)]) 



class CmdFailedErr(RuntimeError):
    pass


class TargetExistsErr(RuntimeError):
    pass


class NotFileErr(RuntimeError):
    pass


class DepIsGenerated(RuntimeError):
    pass

class LineParseErr(RuntimeError):
    pass


class CmdExecuter:
    def __init__(self, target, sources, cmd):
        self.target = target
        self.sources = sources
        self.cmd: Cmd = cmd
        self.dep_files = None
        self.is_ok = False
        self.is_from_cache = False
        
        # cache state
        """ in """
        self.deps_hash = None
        self.metadata_hash = None
        self.cmd_hash = None
        """ out """
        self.dep_files_hashes = dict()
    
    def _check_in_root(self, check_str: str):
        if check_str[0] == "/":
            if check_str.startswith("/tmp/") or check_str.startswith("/dev/") or check_str.startswith("/proc/"):
                return None
            return check_str
        return join(ROOT, check_str)

    def _parse_open(self, raw_path, args):
        """
        1234 open("/lib/x86_64-linux-gnu/libselinux.so.1", O_RDONLY|O_CLOEXEC) = 3
        1234 open("/home/dn/cheetah/lib/libc.so.6", O_RDONLY|O_CLOEXEC) = -1 ENOENT (No such file or directory)
        """
        rc_index = 5 if args[4] == "=" else 4
        rc = int(args[rc_index])
        if not rc >= 0:
            return None
        path = raw_path.split('"')[1]
        return self._check_in_root(path)

    def _parse_openat(self, raw_path, args):
        """
        21456 openat(AT_FDCWD, "/proc/sys/net/core/somaxconn", O_RDONLY|O_CLOEXEC) = 3
        21460 openat(AT_FDCWD, "/home/dn/umake/test/.dockerignore", O_RDONLY|O_CLOEXEC) = -1 ENOENT (No such file or directory)
        1168 openat(AT_FDCWD, "/usr/lib/x86_64-linux-gnu/libopcodes-2.30-system.so", O_RDONLY|O_CLOEXEC <unfinished ...>
        """
        if "<unfinished" == args[4]:
            out.print_fail(f"unfinished: {args[0]} {args[2]}")
            return None
        rc_index = 6 if args[5] == "=" else 5
        rc = int(args[rc_index])
        if not rc >= 0:
            return None
        path = args[2].split('"')[1]
        return self._check_in_root(path)

    def _get_cache(self):
        if self.deps_hash is None:
            return False
        cache_src = join(UMAKE_BUILD_CACHE_DIR, self.deps_hash.hex())
        try:
            for target in self.target:
                f = hashlib.md5(target.encode("ascii")).hexdigest()
                src = join(cache_src, f)
                shutil.copyfile(src, target)
                shutil.copymode(src, target)
        except FileNotFoundError:
            out.print_fail(f"Corrupted cache: file {f} not exists in {cache_src}. clearing")
            shutil.rmtree(cache_src, ignore_errors=True)
            return False
            
        return True

    def _save_cache(self):
        deps_hash = self.cmd_hash
        for dep in self.dep_files:
            deps_hash = byte_xor(deps_hash, self.dep_files_hashes[dep])
        cache_dst = join(UMAKE_BUILD_CACHE_DIR, deps_hash.hex())
        fd, lock_path = fs_lock(cache_dst)
        if fd == None:
            return
        try:
            shutil.rmtree(cache_dst, ignore_errors=True)
            os.mkdir(cache_dst)
            for target in self.target:
                dst = join(cache_dst, hashlib.md5(target.encode("ascii")).hexdigest())
                shutil.copyfile(target, dst)
                shutil.copymode(target, dst)
        finally:
            fs_unlock(fd, lock_path)

    def make(self):
        tmp_unique_name_full_path = join(UMKAE_TMP_DIR, str(uuid.uuid1()))
        with Timer(self.cmd.compile_show()) as timer:
            if self.target and self._get_cache():
                timer.set_prefix("[FROM-CACHE]")
                self.is_ok = True
                self.is_from_cache = True
                return
            strace = f"strace -o{tmp_unique_name_full_path} -f -e open,openat "
            full_cmd = strace + self.cmd.cmd
            self.proc = Popen(full_cmd, env=MINIMAL_ENV, shell=True, stdout=PIPE, stderr=PIPE)
            
            while True:
                try:
                    self.proc.wait(timeout=3)
                    break
                except TimeoutExpired:
                    out.curr_job = self.cmd.compile_show()
                    out.update_bar()
            rc = self.proc.poll()
            if rc != 0:
                out.print_neutarl(self.proc.stdout.read().decode("utf-8"))
                out.print_fail(self.proc.stderr.read().decode("utf-8"))
                # TODO: print here the source of the command
            else:
                self.is_ok = True

            self.dep_files = set()
            with open(tmp_unique_name_full_path) as strace_output:
                for line in strace_output.readlines():
                    args = line.split()
                    raw_path = args[1]
                    if not (raw_path.startswith('open(') or raw_path.startswith('openat(')):
                        continue
                    if raw_path.startswith('open('):
                        full_path = self._parse_open(raw_path, args)
                    else:
                        full_path = self._parse_openat(raw_path, args)

                    if full_path is None:
                        continue
                    full_path = os.path.abspath(full_path)
                    if full_path in self.dep_files:
                        continue
                    try:
                        self.dep_files_hashes[full_path] = FileEntry.file_md5sum(full_path)
                    except IsADirectoryError:
                        continue
                    self.dep_files.add(full_path)
            if self.target:
                if not self.target.issubset(self.dep_files):
                    raise RuntimeError(f"Target not generated: Expcted {self.target} Got: {self.dep_files}")
                self.dep_files -= self.target
            
            if self.target:
                self._save_cache()
                timer.set_prefix("[CACHED]")
        
    def get_results(self):
        return self.dep_files, self.target


class FileEntry:

    class EntryType(Enum):
        GENERATED = auto()
        CMD = auto()
        FILE = auto()

    def __init__(self, full_path, entry_type, data=None):
        self.full_path = full_path
        self.entry_type: FileEntry.EntryType = entry_type
        self.mtime = 0
        self.md5sum = None
        self.is_modified = True
        self.is_refreshed = False
        self.data: Cmd = data
        self.dependencies_built = 0

        if entry_type not in [self.EntryType.CMD, self.EntryType.GENERATED]:
            self.update()
        if entry_type == self.EntryType.CMD:
            self.update_cmd()

    def init(self):
        self.dependencies_built = 0
        self.set_modified(False)
        self.set_refreshed(False)

    def set_refreshed(self, new_value):
        self.is_refreshed = new_value

    def set_modified(self, new_value: bool):
        self.is_modified = new_value
    
    def increase_dependencies_built(self, inc: int):
        self.dependencies_built += inc

    def update_cmd(self):
        self.md5sum = hashlib.md5(self.full_path.encode("ascii")).digest()

    @staticmethod
    def file_md5sum(full_path):
        with open(full_path, "rb") as file_to_check:
            data = file_to_check.read()    
            md5_returned = hashlib.md5(data).digest()
            return md5_returned

    def update(self):
        modified = False
        stat = os.stat(self.full_path)
        if S_ISDIR(stat.st_mode):
            raise NotFileErr(f"failed to get info for {self.full_path}")
        new_mtime = int(stat.st_mtime)
        if new_mtime != self.mtime:
            new_md5sum = self.file_md5sum(self.full_path)
            if new_md5sum != self.md5sum:
                self.set_modified(True)
                modified = True

            self.md5sum  = new_md5sum
        self.mtime = new_mtime
        return modified
    
    def update_with_md5sum(self, new_md5sum):
        stat = os.stat(self.full_path)
        self.mtime = int(stat.st_mtime)
        self.md5sum = new_md5sum

    def __str__(self):
        return f"{self.full_path}: {self.mtime} {self.md5sum}"
    
    def __repr__(self):
        return f"['{self.full_path}': '{self.is_modified}']"
        #return f"['{self.full_path}', '{self.mtime}', '{self.md5sum.hex()}']"


class Line:
    def __init__(self, filename, line_num, line):
        self.filename = filename
        self.line_num = line_num
        self.line = line
    
    def __str__(self):
        return f"{self.filename}:{self.line_num}\n\t{self.line}"


class Cmd:

    def __init__(self, cmd, dep, manual_deps, target, line):
        self.cmd = cmd
        self.dep = dep
        self.manual_deps = manual_deps
        self.conf_deps = set(dep)
        self.target: set = target

        self.line: Line = line

    def compile_show(self):
        return " ".join(sorted(self.target))

    def update(self, other):
        self.line = other.line
    
    def __eq__(self, other):
        return self.cmd == other.cmd and \
               self.dep == other.dep and \
               self.target == other.target


class GraphDB:

    def __init__(self):
        self.nodes = dict() 
        self.graph = igraph.Graph(directed=True)

    def is_exists(self, node):
        return node in self.nodes
    
    def add_node(self, node, data: FileEntry):
        if node not in self.nodes:
            self.graph.add_vertex(node)
        self.nodes[node] = data
    
    def add_connection(self, from_node, to_node):
        # print(f"adding connection {from_node} -> {to_node}")
        if not self.graph.are_connected(from_node, to_node):
            self.graph.add_edge(from_node, to_node)
    
    def add_connections(self, connections):
        # print(f"adding connection {from_node} -> {to_node}")
        self.graph.add_edges(connections)
    
    def get_data(self, node) -> FileEntry:
        return self.nodes[node]

    def dump_graph(self):
        with open(UMAKE_DB, "wb") as db_file:
            pickle.dump(self, db_file, protocol=pickle.HIGHEST_PROTOCOL)

    @staticmethod
    def load_graph():
        try:
            with open(UMAKE_DB, "rb") as db_file:
                data = pickle.load(db_file)
                return data
        except FileNotFoundError:
            return GraphDB()
    
    def get_nodes(self):
        return self.nodes.keys()

    def predecessors(self, node):
        for pred in self.graph.vs.find(node).predecessors():
            yield pred["name"]

    def successors(self, node):
        for succ in self.graph.vs.find(node).successors():
            yield succ["name"]

    def remove_node(self, node):
        del self.nodes[node]
        self.graph.delete_vertices(self.graph.vs.find(node).index)
    
    def topological_sort(self):
        for i in self.graph.topological_sorting():
            yield self.graph.vs[i]["name"]


class CmdTemplate:

    def __init__(self, target, cmd, sources_fmt, deps_fmt, line_num, line, foreach, filename):
        self.targets_fmt = target
        self.cmd_fmt = cmd
        self.sources_fmt = sources_fmt
        self.deps_fmt = deps_fmt
        self.line = Line(filename, line_num, line)
        self.foreach = foreach
        self.root = os.path.dirname(filename)

        self.cmds = list()
        self.fs_files = set()

    def _iterate_file_glob(self, graph: GraphDB, fmt):
        import glob
        files = set()
        for f in glob.iglob(fmt, recursive=True):
            full_path = os.path.abspath(join(self.root, f))
            #  check if the cmd of the target will going to be deleted
            if graph.is_exists(full_path):
                fentry: FileEntry
                fentry = graph.get_data(full_path)
                if fentry.entry_type == FileEntry.EntryType.GENERATED and \
                   fentry.is_refreshed == False:
                    continue
            self.fs_files.add(full_path)
            files.add(full_path)
        return files

    def create_cmds(self, graph: GraphDB, all_targets: set):
        full_path = None
        target = None
        manual_deps = set()
        for dep_fmt in self.deps_fmt:
            added = False
            for global_target in all_targets:
                dep_fmt_fullpath = join(self.root, dep_fmt)
                if fnmatch.fnmatch(global_target, dep_fmt_fullpath):
                    manual_deps.add(global_target)
                    added = True
        
            if added == False:
                raise RuntimeError(f"{self.line}: manual dep '{self.deps_fmt}' is not exists as target in other commands")

        if self.foreach:
            for source_fmt in self.sources_fmt:
                dep_global_target = set()
                for global_target in all_targets:
                    src_fmt_fullpath = join(self.root, source_fmt)
                    if fnmatch.fnmatch(global_target, src_fmt_fullpath):
                        manual_deps.add(global_target)
                        dep_global_target.add(global_target)
                
                files = self._iterate_file_glob(graph, source_fmt)
                files.update(dep_global_target)
                for full_path in files:
                    # print(f"{source_fmt}: {source}")
                    deps = set()
                    deps.update(manual_deps)
                    deps.add(full_path)
                    basename = os.path.basename(full_path)
                    noext = os.path.splitext(basename)[0]
                    if self.targets_fmt:
                        targets = set()
                        for target_fmt in self.targets_fmt:
                            target = target_fmt.format(filename=full_path,
                                                        dir=os.path.dirname(full_path),
                                                        basename=basename,
                                                        noext=noext)
                            target = os.path.abspath(join(self.root, target))
                            targets.add(target)
                            if target in all_targets:
                                raise RuntimeError(f"Failed parsing {self.line}\nTarget {target} already exists, two commands can't generate same target")
                            all_targets.add(target)
                        cmd = self.cmd_fmt.format(filename=full_path,
                                                dir=os.path.dirname(full_path),
                                                basename=os.path.basename(full_path),
                                                noext=noext,
                                                target=target)
                        # print(targets)
                        self.cmds.append(Cmd(cmd, deps, manual_deps, targets, self.line))
                    else:
                        cmd = self.cmd_fmt.format(filename=full_path,
                                                    dir=os.path.dirname(full_path),
                                                    basename=os.path.basename(full_path),
                                                    noext=noext)
                        self.cmds.append(Cmd(cmd, deps, manual_deps, {}, self.line))
        else:
            deps = set()
            deps.update(manual_deps)
            sources = set()
            for source_fmt in self.sources_fmt:
                for full_path in self._iterate_file_glob(graph, source_fmt):
                    sources.add(full_path)

                source_fmt_fullpath = join(self.root, source_fmt)
                source_dir = os.path.dirname(source_fmt_fullpath)
                for global_target in all_targets:
                    target_dir = os.path.dirname(global_target)
                    if source_dir != target_dir:
                        # we checking only in the current directory
                        continue
                    if fnmatch.fnmatch(global_target, source_fmt_fullpath):
                        sources.add(global_target)

            targets = set()
            if self.targets_fmt:
                basename = None
                noext = None
                dirname = None
                if full_path is not None:
                    basename = os.path.basename(full_path)
                    noext = os.path.splitext(basename)[0]
                    dirname = os.path.dirname(full_path)

                for target_fmt in self.targets_fmt:
                    target = target_fmt.format(filename=full_path,
                                            dir=dirname,
                                            basename=basename,
                                            noext=noext)
                    targets.add(join(self.root, target))
                target_exists = targets.intersection(all_targets)
                if target_exists:
                    raise RuntimeError("Target {target_exists} already exists, two commands can't generate same target")
            all_targets.update(targets)
            cmd = self.cmd_fmt.format(filename=" ".join(sorted(sources)),
                                      target=" ".join(sorted(targets)))
            deps.update(sources)
            self.cmds.append(Cmd(cmd, deps, manual_deps, targets, self.line))
        

def find_between(string, token_start, token_end):
    state = "find_token_start"
    start_idx = None
    for idx, ch in enumerate(string):
        if state == "find_token_start":
            if ch == token_start:
                state = "find_token_end"
                start_idx = idx
        elif state == "find_token_end":
            if ch == token_end or idx == len(string) - 1:
                token = string[start_idx:idx+1].strip()
                if not token == "":
                    yield token
                state = "find_token_start"


class UMakeFileParser():
    """
    HELLO = 1
    : a.c > gcc {filename} -o {target} > {filename}.o  
    : > gcc {filename} -o {target} > {filename}.o  
    :foreach *.c > gcc {filename} -o {target} > {basename}.o  
    :foreach | sdf > gcc {filename} -o {target} > {basename}.o  
    """
    def __init__(self, filename):
        self.fielanme = filename
        self.umakefile = None
        self.cmds_template: [CmdTemplate] = []

        self.load_file()
        self.parse_file()
    
    def load_file(self):
        with open(self.fielanme, mode="r") as umakefile:
            self.umakefile = umakefile.read()

    def parse_file(self):
        macros = dict()
        globals_vars = dict()
        for line_num, line in enumerate(self.umakefile.splitlines()):
            try:
                foreach = False
                deps_fmt = []
                source_fmt = []
                
                if line == "" or line[0] == "#":
                    continue
                
                if line[0] == ":":
                    for macro_call in find_between(line, "!", ")"):
                        """ macro call - !gcc($x,$y,$z)"""
                        macro_name, macro_args_sent = macro_call.split("(", 1)
                        macro_args = macros[macro_name][0]
                        macro_args_sent = macro_args_sent[:-1].split(",")
                        macro_body = macros[macro_name][1]
                        if macro_args_sent == ['']:
                            macro_args_sent = []
                        if len(macro_args_sent) != len(macro_args):
                            raise RuntimeError(f"macro {macro_name} has {len(macro_args)} args but called with {len(macro_args_sent)}")
                        for idx, sent_arg in enumerate(macro_args_sent):
                            sent_arg = sent_arg.strip()
                            try:
                                if sent_arg == "":
                                    send_arg_value = ""
                                elif sent_arg[0] == "$":
                                    send_arg_value = globals_vars[sent_arg]
                                else:
                                    send_arg_value = sent_arg
                            except KeyError:
                                raise RuntimeError(f"macro {macro} called with not exists arg: {send_arg}")
                            in_macro_args = macro_args[idx]
                            macro_body = macro_body.replace(in_macro_args, send_arg_value)

                        line = line.replace(macro_call, macro_body)
                    sources_cand, cmd_fmt, targets_fmt = line.split(">")
                    sources_cand = sources_cand.split()
                    targets_fmt = targets_fmt.split()
                    if len(sources_cand) == 1:
                        pass
                        # No sources
                    else:
                        deps_index = len(sources_cand)
                        try:
                            deps_index = sources_cand.index("|")
                            deps_fmt = sources_cand[deps_index + 1:]
                        except ValueError:
                            pass

                        foreach = True if sources_cand[0] == ":foreach" else False
                        source_fmt = sources_cand[1:deps_index]
                    self.cmds_template.append(CmdTemplate(targets_fmt, cmd_fmt.strip(), source_fmt, deps_fmt, line_num, line, foreach, self.fielanme))
                elif line[0] == "!":
                    args = list()               
                    """ !compile-c(a, b, c) = gcc -c -fPIC {filename} -o {target} > {dir}/{noext}.o """
                    macro_decl, macro_body = line.split("=", 1)
                    macro_decl = macro_decl.replace(" ", "")
                    macro_name, marco_args = macro_decl.strip().split("(")
                    marco_args = marco_args[:-1]  # remove ending )
                    marco_args = marco_args.split(",")
                    if marco_args != ['']:
                        for arg in marco_args:
                            args.append(f"${arg}")
                    macros[macro_name] = (args, macro_body.strip())
                elif line[0] == "$":
                    var_name, var_body = line.split("=", 1)
                    for var_to_replace in find_between(var_body, "$", " "):
                        var_body = var_body.replace(var_to_replace, globals_vars[var_to_replace])
                    globals_vars[var_name.strip()] = var_body.strip()
                    

            except:
                out.print_fail(f"ERROR failed to parse UMakefile")
                out.print_fail(f"{self.fielanme}:{line_num}")
                out.print_fail(f"   {line}")
                raise


class UMake:

    def __init__(self):

        shutil.rmtree(UMKAE_TMP_DIR, ignore_errors=True)
        os.makedirs(UMKAE_TMP_DIR, exist_ok=True)
        os.makedirs(UMAKE_BUILD_CACHE_DIR, exist_ok=True)

        self.graph = None
        self.cmds = set()
        self.generated = set()
        self.files = set()

        self._start_executer_thread()
    
    def _start_executer_thread(self):
        self.jobs_queue = Queue() # CmdExecuter
        self.done_queue = Queue()
        self.n_jobs = 0
        for _ in range(UMAKE_MAX_WORKERS):
            exec_thread = threading.Thread(target=self.executer_thread, daemon=True)
            exec_thread.start()

    def _get_file_entry(self, full_path):
        return FileEntry(full_path, FileEntry.EntryType.FILE)

    def _is_in_blacklist(self, path):
        if "/." in path:
            return True
        if path[0] == '.':
            return True
        return False

    def _iterate_all_files(self):
        for (dirpath, dirnames, filenames) in os.walk(ROOT, followlinks=True):
            if self._is_in_blacklist(dirpath):
                continue
            for filename in filenames:
                if self._is_in_blacklist(filename):
                    continue
                yield os.path.join(dirpath, filename)

    def _remove_generated_from_graph(self, deleted_gen):
        out.print_file_deleted(deleted_gen)
        fentry = self.graph.get_data(deleted_gen)
        fentry.set_modified(True)
        for pred_deleted_gen in self.graph.predecessors(deleted_gen):
            fentry = self.graph.get_data(pred_deleted_gen)
            fentry.set_modified(True)
        self.graph.remove_node(deleted_gen)

    def _remove_file_from_graph(self, delete_file, deleted):
        succs = list(self.graph.successors(delete_file))
        for succ in succs:
            fentry = self.graph.get_data(succ)
            if fentry.entry_type == FileEntry.EntryType.CMD:
                targets = list(self.graph.successors(succ))
                for target in targets:
                    deleted.add(target)
                    self._remove_generated_from_graph(target)
                    self._remove_from_fs(target)

        out.print_file_deleted(delete_file)
        self.graph.remove_node(delete_file)

    def scan_fs(self):
        with Timer("done filesystem scan"):
            graph_fs = list(chain(self.files, self.generated))
            deleted = set()

            for f in graph_fs:
                if f in deleted:
                    continue
                fentry: FileEntry = self.graph.get_data(f)
                try:
                    if fentry.update():
                        for pred_deleted_gen in self.graph.predecessors(f):
                            pred_entry = self.graph.get_data(pred_deleted_gen)
                            pred_entry.set_modified(True)
                        out.print_file_updated(f)
                except FileNotFoundError:
                    if fentry.entry_type == FileEntry.EntryType.GENERATED:
                        self._remove_generated_from_graph(f)
                        deleted.add(f)
                    elif fentry.entry_type == FileEntry.EntryType.FILE:
                        self._remove_file_from_graph(f, deleted)
                        deleted.add(f)
                    else:
                        raise RuntimeError("how can it be???")

    def _graph_remove_cmd_node(self, cmd: Cmd):
        # import itertools
        # fentry: FileEntry = self.graph.nodes[cmd.cmd]["fentry"]

        # succ = self.graph.successors(cmd.cmd)
        # pred = self.graph.predecessors(cmd.cmd)
        self.graph.remove_node(cmd.cmd)
        # for node in itertools.chain(succ, pred):
        #     no_succ = False
        #     no_pred = False
        #     try:
        #         next(self.graph.successors(node))
        #     except StopIteration:
        #         no_succ = True
        #     try:
        #         next(self.graph.predecessors(node))
        #     except StopIteration:
        #         no_pred = True
        #     if no_succ and no_pred:
        #         self.graph.remove_node()
    
    def _graph_add_cmd_node(self, cmd: Cmd):
        fentry_cmd = FileEntry(cmd.cmd, FileEntry.EntryType.CMD, cmd)
        self.graph.add_node(cmd.cmd, fentry_cmd)
        for target in cmd.target:
            self.graph.add_node(target, FileEntry(target, FileEntry.EntryType.GENERATED, cmd))
            self.graph.add_connection(cmd.cmd, target)
        for dep in cmd.dep:
            self.graph.add_connection(dep, cmd.cmd)

    def _graph_update_cmd_node(self, old_cmd: Cmd, new_cmd: Cmd, fentry_cmd: FileEntry):
        if old_cmd != new_cmd:
            self._graph_remove_cmd_node(old_cmd)
            self._graph_add_cmd_node(new_cmd)
        else:
            old_cmd.update(new_cmd)

        for target in new_cmd.target:
            if not self.graph.is_exists(target):
                self.graph.add_node(target, FileEntry(target, FileEntry.EntryType.GENERATED, new_cmd))
            self.graph.add_connection(new_cmd.cmd, target)
        
        for dep in new_cmd.dep:
            self.graph.add_connection(dep, new_cmd.cmd)

    def _remove_from_fs(self, filename):
        out.print_file_deleted(filename, "DELETING")
        os.remove(filename)

    def parse_cmd_files(self):
        with Timer("done parsing UMakefile"):
            all_targets = set()
            UMakefile = join(ROOT , "UMakefile")
            umakefile = UMakeFileParser(UMakefile)

            cmd_template: CmdTemplate
            cmds = set()
            for cmd_template in umakefile.cmds_template:
                cmd_template.create_cmds(self.graph, all_targets)
                cmd: Cmd
                for f in cmd_template.fs_files:
                    if not self.graph.is_exists(f):
                        new_fentry = self._get_file_entry(f)
                        out.print_file_add(f)
                        self.graph.add_node(f, new_fentry)
                for cmd in cmd_template.cmds:
                    if self.graph.is_exists(cmd.cmd):
                        cmd_fentry = self.graph.get_data(cmd.cmd)
                        cmd_fentry.set_refreshed(True)
                    cmds.add(cmd.cmd)

            removed_cmds = self.cmds.difference(cmds)
            
            for remove_cmd in removed_cmds:
                remove_cmd_list = list(self.graph.successors(remove_cmd))
                for target_file in remove_cmd_list:
                    if self.graph.is_exists(target_file):
                        succseccors = self.graph.successors(target_file)
                        for succ in succseccors:
                            fentry = self.graph.get_data(succ)
                            fentry.data.dep.remove(target_file)

                        self.graph.remove_node(target_file)
                        self._remove_from_fs(target_file)
                self.graph.remove_node(remove_cmd)
            
            for cmd_template in umakefile.cmds_template:
                for cmd in cmd_template.cmds:
                    if cmd.cmd in removed_cmds:
                        continue
                    if cmd.cmd in self.cmds:
                        fentry_cmd: FileEntry = self.graph.get_data(cmd.cmd)
                        self._graph_update_cmd_node(fentry_cmd.data, cmd, fentry_cmd)
                    else:
                        self._graph_add_cmd_node(cmd)

            self.cmds = cmds 
    
    def executer_thread(self):
        while True:
            executer: CmdExecuter
            executer = self.jobs_queue.get()
            out.n_active_workers.inc()
            out.curr_job = executer.cmd.compile_show()
            # out.update_bar()
            out.print(f"{executer.cmd.cmd}")
            try:
                executer.make()
            except Exception as e:
                import traceback
                traceback.print_exc()
                out.print(e)
                executer.is_ok = False
            out.n_active_workers.dec()
            # out.update_bar()
            self.done_queue.put(executer)

    def _handle_done(self):
        execucter: CmdExecuter
        execucter = self.done_queue.get()
        self.n_jobs -= 1
        if execucter.is_ok is False:
            raise CmdFailedErr(f"command failed: {execucter.cmd.line}\n cmd:\n\t {execucter.cmd.cmd}")
        
        deps, targets = execucter.get_results()
        node = execucter.cmd.cmd

        node_entry: FileEntry = self.graph.get_data(node)
        node_entry.set_modified(False)
        out.n_works_done += 1
        if execucter.is_from_cache:
            out.n_cache_hits += 1
        conns = []
        for dep in deps:
            if self.graph.is_exists(dep):
                dep_fentry: FileEntry = self.graph.get_data(dep)
                if dep_fentry.entry_type == FileEntry.EntryType.GENERATED and dep not in self.graph.predecessors(node):
                    out.print_fail(f"at line: {execucter.cmd.line}")
                    out.print_fail(f"\t'{node}' :\n have generated dependency '{dep}'")
                    out.print_fail(f"from line: {dep_fentry.data.line}")
                    out.print_fail(f"add to line: {execucter.cmd.line}")
                    out.print_fail(f"{dep} as a manual dependency")
                    raise DepIsGenerated()
                if execucter.dep_files_hashes:
                    dep_fentry.update_with_md5sum(execucter.dep_files_hashes[dep])
                else:
                    dep_fentry.update()
            else:
                try:
                    fentry = FileEntry(dep, FileEntry.EntryType.FILE)
                except NotFileErr as e:
                    out.print(e)
                    continue
                self.graph.add_node(dep, fentry)
            
            if not self.graph.graph.are_connected(dep, node):
                conns.append((dep, node))
        self.graph.add_connections(conns)
        
        for target in targets:
            target_node = self.graph.get_data(target)
            target_node.increase_dependencies_built(-1)
            target_node.update()
        
        if targets:
            self._set_deps_hash(node_entry, execucter)

        if self.n_jobs == 0:
            return False
        else:
            return True

    def _calc_hash(self, cmd_hash, deps):
        tree_hash = cmd_hash
        for dep in deps:
            with Timer(f"hash {dep}", threshold=0.05, color=bcolors.FAIL):
                try:
                    fentry: FileEntry = self.graph.get_data(dep)
                except KeyError:
                    fentry = self._get_file_entry(dep)
                    self.graph.add_node(dep, fentry)
                    out.print_file_add(dep)
                tree_hash = byte_xor(tree_hash, fentry.md5sum)
        return tree_hash

    def _set_deps_hash(self, node_entry, execucter: CmdExecuter):
        metadata_hash = execucter.metadata_hash
        save_cache(metadata_hash, MetadataCache(execucter.dep_files))

    def _get_deps_hash(self, node_entry):
        metadata_hash = self._calc_hash(node_entry.md5sum, node_entry.data.conf_deps)
        if not node_entry.data.target:
            return None, None, metadata_hash
        try:
            metadata = open_cache(metadata_hash)
            deps_hash = self._calc_hash(node_entry.md5sum, metadata.deps)
            return deps_hash, metadata.deps, metadata_hash
        except FileNotFoundError:
            return None, None, metadata_hash

    def execute_graph(self):
        top_sort = list(self.graph.topological_sort())
        for node in top_sort:
            node_entry: FileEntry = self.graph.get_data(node)
            # print(node_entry)
            if not node_entry.is_modified:
                continue
            while node_entry.dependencies_built > 0:
                self._handle_done()
            
            successors = set()
            for succ in self.graph.successors(node):
                succ_node = self.graph.get_data(succ)
                succ_node.set_modified(True)
                if node_entry.entry_type == FileEntry.EntryType.CMD:
                    succ_node.increase_dependencies_built(1)
                successors.add(succ)
            if node_entry.entry_type == FileEntry.EntryType.CMD:
                deps_hash, cached_deps, metadata_hash = self._get_deps_hash(node_entry)
                execucter = CmdExecuter(successors, "", node_entry.data)
                
                execucter.cmd_hash = node_entry.md5sum
                execucter.metadata_hash = metadata_hash
                execucter.deps_hash = deps_hash
                execucter.dep_files = cached_deps
                self.jobs_queue.put(execucter)
                self.n_jobs += 1
        
        if self.n_jobs:
            while self._handle_done():
                pass
            
    def dump_graph(self):
        # with Timer("done prettyprint"):
            # for n in self.graph.graph.vs:
            #     if self.graph.graph.vs.find(n.index).predecessors():
            #         prec = [f"\t {n['name']} {n.index}\n" for n in self.graph.graph.vs.find(n.index).predecessors()]
            #         print(f"{n['name']} <- \n {''.join(prec)}")
        with Timer("done saving graph"):
            self.graph.dump_graph()

    def load_graph(self):
        with Timer("done loading graph"):
            self.graph = GraphDB.load_graph()
            for node in self.graph.get_nodes():
                fentry: FileEntry = self.graph.get_data(node)
                if fentry.entry_type == FileEntry.EntryType.CMD:
                    self.cmds.add(node)
                elif fentry.entry_type == FileEntry.EntryType.GENERATED:
                    self.generated.add(node)
                elif fentry.entry_type == FileEntry.EntryType.FILE:
                    self.files.add(node)
                fentry.init()

    def cache_gc(self):
    
        def remove(path):
            """ param <path> could either be relative or absolute. """
            if os.path.isfile(path):
                os.remove(path)  # remove the file
            elif os.path.isdir(path):
                shutil.rmtree(path)  # remove dir and all contains
            else:
                raise ValueError("file {} is not a file or dir.".format(path))

        with Timer("done cache gc") as timer:
            cache_dir_size_KB = get_size_KB(UMAKE_BUILD_CACHE_DIR)
            high_thresh = cache_dir_size_KB * 1.1
            low_tresh = UMAKE_BUILD_CACHE_MAX_SIZE_MB * 1024 * 0.6
            
            if UMAKE_BUILD_CACHE_MAX_SIZE_MB * 1024 > high_thresh:
                return
            
            fd, lock_path = fs_lock(UMAKE_BUILD_CACHE_DIR)
            if fd == None:
                out.print_fail(f"\tcahce: {UMAKE_BUILD_CACHE_LOCK} is locked")
                return
            try:
                cache_dir = check_output(['ls', '-lru', '--sort=time', UMAKE_BUILD_CACHE_DIR]).decode('utf-8')
                for cache_line in cache_dir.splitlines():
                    try:
                        _, _, _, _, _, _, _, _, cache_entry_name = cache_line.split()
                        cache_entry_full_path = join(UMAKE_BUILD_CACHE_DIR, cache_entry_name)
                        remove(cache_entry_full_path)
                        cache_entry_size = get_size_KB(UMAKE_BUILD_CACHE_DIR)
                        if cache_entry_size < low_tresh:
                            break
                    except ValueError:
                        pass
                timer.set_postfix(f" freed {(cache_dir_size_KB - cache_entry_size) / 1024}MB")
            finally:
                fs_unlock(fd, lock_path)

    def run(self):
        # profiler.start()
        umake.load_graph()
        umake.scan_fs()
        umake.parse_cmd_files()
        umake.execute_graph()
        umake.dump_graph()
        umake.cache_gc()
        out.update_bar(force=True)
        out.destroy()
        # profiler.stop()

    def show_target_details(self, target):
        target_fentry: FileEntry
        target_fentry = self.graph.get_data(target)
        
        cmd = target_fentry.data.cmd
        all_deps = set(self.graph.predecessors(cmd))
        
        configured_deps = sorted(target_fentry.data.dep - target_fentry.data.manual_deps)
        manual_deps = sorted(target_fentry.data.manual_deps)
        auto_deps = all_deps - target_fentry.data.dep
        auto_dep_in_project = set()
        for auto_dep in auto_deps:
            if fnmatch.fnmatch(auto_dep, ROOT + "/*"):
                auto_dep_in_project.add(auto_dep)
        global_auto_deps = sorted(auto_deps - auto_dep_in_project)
        auto_dep_in_project = sorted(auto_dep_in_project)
        successors = set(self.graph.successors(target))
        
        if global_config.json_file:
            with open(global_config.json_file, "w") as f:
                import json
                out_json = dict()
                deps = dict()
                deps["configured"] = configured_deps
                deps["manual"] = manual_deps
                deps["auto_in"] = auto_dep_in_project
                deps["auto_global"] = global_auto_deps
                out_json["target"] = target
                out_json["deps"] = deps
                out_json["cmd"] = target_fentry.data.cmd

                f.write(json.dumps(out_json))
        else:
            out.print_colored(f"{target}:", bcolors.HEADER)
            print("\tdeps:")
            for dep in configured_deps:
                print(f"\t\t{dep}")
            for dep in manual_deps:
                out.print_colored(f"\t\t{dep}", bcolors.WARNING)
            for dep in auto_dep_in_project:
                out.print_colored(f"\t\t{dep}", bcolors.OKGREEN)
            for dep in global_auto_deps:
                out.print_colored(f"\t\t{dep}", bcolors.OKBLUE)
            print()
            print("\tsuccessors targets:")
            for succ in successors:
                succ_targets = " ".join(sorted(set(self.graph.successors(succ))))
                print(f"\t\t{succ_targets}")
            print()
            print("\tcmd:")
            print(f'\t\t{target_fentry.data.cmd}')
            print()

    def show_targets_details(self, target):
        for graph_target in self.generated:
            if fnmatch.fnmatch(graph_target, target):
                self.show_target_details(graph_target)

    def show_target_details_run(self, target):
        umake.load_graph()
        umake.parse_cmd_files()
        self.show_targets_details(target)
        
        
        
        

umake = UMake()
if len(sys.argv) == 1:
    umake.run()
else:
    import argparse
    parser = argparse.ArgumentParser()

    parser.add_argument('target', type=str,
                        help='target path')

    parser.add_argument('--details', action='store_true',
                        help='details about the target')
    parser.add_argument('--json', action='store', dest='json_file',
                        help='output as json')

    args = parser.parse_args()

    if args.json_file:
        global_config.json_file = args.json_file

    if args.details:
        args.target = join(ROOT, args.target) + "**"
        umake.show_target_details_run(args.target)
    

# print(profiler.output_text(color=True))