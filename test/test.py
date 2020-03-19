import unittest
from subprocess import check_output, Popen
import subprocess
import shutil
import os
import json
import time
from minio import Minio
import minio

ROOT = os.getcwd()
COVERAGE_DIR_PATH = os.path.join(ROOT, 'coverage')
COVEARAGE_CMD = "coverage-3.6 run -a"
UMAKE_BIN = f"{ROOT}/../umake/umake"

class Timer:
    def __init__(self, msg, iterations):
        self.msg = msg
        self.iterations = iterations

    def __enter__(self):
        self.start = time.time()
        return self

    def __exit__(self, *args):
        self.end = time.time()
        interavl = self.end - self.start 
        print(f"[{interavl:.3f}] [{interavl/self.iterations:.5f} per iter] {self.msg}")

class TestUMake(unittest.TestCase):

    def setUp(self):
        shutil.rmtree("env", ignore_errors=True)
        os.mkdir("env")
        os.mkdir("env/proto")
        try:
            check_output("pkill -9 minio", shell=True)
        except subprocess.CalledProcessError:
            pass

    @classmethod
    def setUpClass(cls):
        os.environ['COVERAGE_FILE'] = os.path.join(COVERAGE_DIR_PATH, ".coverage")

    @classmethod
    def tearDownClass(cls):
        print(f"\nCreating coverage xml from coverage/.coverage")
        check_output(f"coverage-3.6 xml -i -o {os.path.join(COVERAGE_DIR_PATH, 'coverage.xml')}", stderr=subprocess.STDOUT, shell=True)


    def _create_setup_simple_umake(self):
        with open('env/a.h', "w") as f:
            f.write("""
            """)

        with open('env/a.c', "w") as f:
            f.write("""
            #include "stdio.h"
            #include "a.h"
            int main()
            {
                printf("hello");
                return 0;
            }
            """)

        with open('env/b.c', "w") as f:
            f.write("""
            #include "stdio.h"
            #include "b.h"
            int hello()
            {
                printf("hello");
                return 0;
            }
            """)

        with open('env/b.h', "w") as f:
            f.write("""
            int hello();
            """)


    def _check_file_exists(self, path, check_timestamp={}, is_changed={}):
        timestamps = dict()
        for p in path:
            full_path = os.path.join("env", p)
            self.assertTrue(os.path.isfile(full_path), msg=f"path {full_path} is {os.path.isfile(full_path)}")

            if len(is_changed):
                timestamps[p] = os.stat(full_path).st_mtime
                if is_changed[p] == True:
                    self.assertNotEqual(check_timestamp[p], timestamps[p])
                else:
                    self.assertEqual(check_timestamp[p], timestamps[p], msg=f"p={p}")
        return timestamps

    def _check_file_not_exists(self, path):
        for p in path:
            self.assertFalse(os.path.isfile(os.path.join("env", p)))

    def _compile(self, umake, variant=[], targets=[], should_fail=False, should_output=True, local_cache=False, remote_cache=False):
        with open('env/UMakefile', "w") as umakefile:
            umakefile.write(umake)
        variant_config = ""
        if variant:
            variant_config = f'--variant {" --variant ".join(variant)}'
        targets_str = ""

        local_cache_conf = "--no-local-cache"
        if local_cache:
            local_cache_conf = ""

        remote_cache_conf="--no-remote-cache"
        if remote_cache:
            remote_cache_conf = ""

        if targets:
            targets_str = " ".join(targets)
       
        try:
            def call():
                return check_output(f"{COVEARAGE_CMD} {UMAKE_BIN} {remote_cache_conf} {local_cache_conf} {variant_config} {targets_str}", cwd="env/", shell=True).decode("utf-8")
            if should_output:
                print(call())
            else:
                call()
            if should_fail:
                self.assertTrue(False, msg="umake compiled although should fail")
        except subprocess.CalledProcessError:
            if should_fail is False:
                self.assertTrue(False, msg="Failed to run umake")

    def _assert_compilation(self, target, deps_conf=None, deps_manual=None, deps_auto_in=None):
        print(check_output(f"{COVEARAGE_CMD} {UMAKE_BIN} {target} --no-local-cache --no-remote-cache --details --json json_out", shell=True, cwd="env/"))
        with open("env/json_out") as f:
            deps = json.load(f)

        deps_conf = [os.path.join(ROOT, "env", dep) for dep in deps_conf]
        self.assertEqual(deps["deps"]["configured"], deps_conf, msg="deps_conf")
        deps_manual = [os.path.join(ROOT, "env", dep) for dep in deps_manual]
        self.assertEqual(deps["deps"]["manual"], deps_manual, msg="deps_manual")
        deps_auto_in = [os.path.join(ROOT, "env", dep) for dep in deps_auto_in]
        self.assertEqual(deps["deps"]["auto_in"], deps_auto_in, msg="deps_auto_in")

    def _rm(self, files):
        for f in files:
            os.remove(os.path.join("env", f))

    def _create(self, path, content):
        parent = os.path.dirname(path)
        if parent not in ["", "/"]:
            check_output(f"mkdir -p env/{parent}", shell=True)
        with open(f'env/{path}', "w") as f:
            f.write(content)
        if path.endswith(".sh"):
            check_output(f"chmod +x env/{path}", shell=True)

    def test_simple_umake(self):
        self._create_setup_simple_umake()
        umake = ":foreach *.c > gcc -g -O2 -Wall -fPIC -c {filename} -o {target} > {dir}/{noext}.o\n"
        umake += ": *.o > gcc -g --shared -O2 -Wall -fPIC {filename} -o {target} > test.so\n"
        self._compile(umake)
        timestamps = {"a.o": 0, "b.o": 0, "test.so": 0}
        is_changed = {"a.o": True, "b.o": True, "test.so": True}
        timestamps = self._check_file_exists(["a.o", "b.o", "test.so"], check_timestamp=timestamps, is_changed=is_changed)
        self._assert_compilation("a.o", deps_conf=["a.c"], deps_manual=[], deps_auto_in=["a.h"])
        self._assert_compilation("b.o", deps_conf=["b.c"], deps_manual=[], deps_auto_in=["b.h"])
        self._assert_compilation("test.so", deps_conf=["a.o", "b.o"], deps_manual=[], deps_auto_in=[])

        """ last target is removed, only the removed target is recompiled """
        self._rm(["test.so"])
        self._compile(umake)
        is_changed = {"a.o": False, "b.o": False, "test.so": True}
        timestamps = self._check_file_exists(["a.o", "b.o", "test.so"], check_timestamp=timestamps, is_changed=is_changed)
        self._assert_compilation("a.o", deps_conf=["a.c"], deps_manual=[], deps_auto_in=["a.h"])
        self._assert_compilation("b.o", deps_conf=["b.c"], deps_manual=[], deps_auto_in=["b.h"])
        self._assert_compilation("test.so", deps_conf=["a.o", "b.o"], deps_manual=[], deps_auto_in=[])

        """ not last target is removed, all targets recompiled """
        self._rm(["a.o", "b.o"])
        self._compile(umake)
        is_changed = {"a.o": True, "b.o": True, "test.so": True}
        timestamps = self._check_file_exists(["a.o", "b.o", "test.so"], check_timestamp=timestamps, is_changed=is_changed)
        self._assert_compilation("a.o", deps_conf=["a.c"], deps_manual=[], deps_auto_in=["a.h"])
        self._assert_compilation("b.o", deps_conf=["b.c"], deps_manual=[], deps_auto_in=["b.h"])
        self._assert_compilation("test.so", deps_conf=["a.o", "b.o"], deps_manual=[], deps_auto_in=[])

        """ source removed, direct target is removed last target recompiled """
        self._rm(["b.c"])
        self._compile(umake)
        is_changed = {"a.o": False, "test.so": True}
        timestamps = self._check_file_exists(["a.o", "test.so"], check_timestamp=timestamps, is_changed=is_changed)
        self._check_file_not_exists(["b.o"])
        self._assert_compilation("a.o", deps_conf=["a.c"], deps_manual=[], deps_auto_in=["a.h"])
        self._assert_compilation("test.so", deps_conf=["a.o"], deps_manual=[], deps_auto_in=[])

        """ source added, directed target add last target recompiled """
        self._create("b.c", """
            #include "stdio.h"
            #include "b.h"
            int hello()
            {
                printf("hello");
                return 0;
            }
            """)
        self._compile(umake)
        is_changed = {"a.o": False, "b.o": True, "test.so": True}
        timestamps["b.o"] = 0
        timestamps = self._check_file_exists(["a.o", "b.o", "test.so"], check_timestamp=timestamps, is_changed=is_changed)
        self._assert_compilation("a.o", deps_conf=["a.c"], deps_manual=[], deps_auto_in=["a.h"])
        self._assert_compilation("b.o", deps_conf=["b.c"], deps_manual=[], deps_auto_in=["b.h"])
        self._assert_compilation("test.so", deps_conf=["a.o", "b.o"], deps_manual=[], deps_auto_in=[])

        """ remove source compilation from UMakefile, all targets should be removed """
        umake = "\n"
        self._compile(umake)
        self._check_file_not_exists(["a.o", "b.o", "test.so"])

        """ compile only sources """
        umake = ":foreach *.c > gcc -g -O2 -Wall -fPIC -c {filename} -o {target} > {dir}/{noext}.o\n"
        self._compile(umake)
        is_changed = {"a.o": True, "b.o": True}
        timestamps = self._check_file_exists(["a.o", "b.o"], check_timestamp=timestamps, is_changed=is_changed)
        self._check_file_not_exists(["test.so"])
        self._assert_compilation("a.o", deps_conf=["a.c"], deps_manual=[], deps_auto_in=["a.h"])
        self._assert_compilation("b.o", deps_conf=["b.c"], deps_manual=[], deps_auto_in=["b.h"])

        # test changing a, a.o, test.so a.h will recompile

    def test_generated_targets(self):

        self._create("proto/a_proto.proto", """
syntax = "proto2";

message data {
    required string str = 1;
}
        """)

        self._create("a_use.h", """
        """)

        self._create("a_use.c", """
#include "proto/a_proto.pb-c.h"
#include "a_use.h"

int hello_gen()
{
    Data data;
    data__init(&data);
    return 0;
}
        """)

        self._create("b_notuse.h", """
        """)

        self._create("b_notuse.c", """
#include "b_notuse.h"

int hellob_gen()
{
    return 0;
}
        """)

        umake  = ":foreach proto/*.proto > protoc-c -I={dir} --c_out={dir} {filename} > {dir}/{noext}.pb-c.c {dir}/{noext}.pb-c.h\n"
        umake += ":foreach proto/*.pb-c.c | proto/a_proto.pb-c.h > gcc -g -O2 -Wall -fPIC -c {filename} -o {target} > {dir}/{noext}.o\n"
        umake += ":foreach a_use.c | proto/a_proto.pb-c.h > gcc -g -O2 -Wall -fPIC -c {filename} -o {target} > {dir}/{noext}.o\n"
        umake += ":foreach b_notuse.c > gcc -g -O2 -Wall -fPIC -c {filename} -o {target} > {dir}/{noext}.o\n"
        umake += ": *.o proto/*.o > gcc -g --shared -O2 -Wall -fPIC {filename} -o {target} > test.so\n"

        self._compile(umake)
        timestamps = {"a_use.o": 0, "b_notuse.o": 0, "proto/a_proto.pb-c.c": 0, "proto/a_proto.pb-c.h": 0, "proto/a_proto.pb-c.o": 0, "test.so": 0}
        is_changed = {"a_use.o": True, "b_notuse.o": True, "proto/a_proto.pb-c.c": True, "proto/a_proto.pb-c.h": True, "proto/a_proto.pb-c.o": True, "test.so": True}
        timestamps = self._check_file_exists(["a_use.o", "b_notuse.o", "proto/a_proto.pb-c.c", "proto/a_proto.pb-c.h", "proto/a_proto.pb-c.o", "test.so"], check_timestamp=timestamps, is_changed=is_changed)
        self._assert_compilation("proto/a_proto.pb-c.c", deps_conf=["proto/a_proto.proto"], deps_manual=[], deps_auto_in=[])
        self._assert_compilation("proto/a_proto.pb-c.h", deps_conf=["proto/a_proto.proto"], deps_manual=[], deps_auto_in=[])
        self._assert_compilation("a_use.o", deps_conf=["a_use.c"], deps_manual=["proto/a_proto.pb-c.h"], deps_auto_in=["a_use.h"])
        self._assert_compilation("b_notuse.o", deps_conf=["b_notuse.c"], deps_manual=[], deps_auto_in=["b_notuse.h"])
        # self._assert_compilation("proto/a_proto.pb-c.o", deps_conf=[], deps_manual=[], deps_auto_in=[])

        self._rm(["proto/a_proto.pb-c.o"])
        self._compile(umake)
        is_changed = {"a_use.o": False, "b_notuse.o": False, "proto/a_proto.pb-c.c": False, "proto/a_proto.pb-c.h": False, "proto/a_proto.pb-c.o": True, "test.so": True}
        timestamps = self._check_file_exists(["a_use.o", "b_notuse.o", "proto/a_proto.pb-c.c", "proto/a_proto.pb-c.h", "proto/a_proto.pb-c.o", "test.so"], check_timestamp=timestamps, is_changed=is_changed)

        self._rm(["proto/a_proto.pb-c.c"])
        self._compile(umake)
        is_changed = {"a_use.o": True, "b_notuse.o": False, "proto/a_proto.pb-c.c": True, "proto/a_proto.pb-c.h": True, "proto/a_proto.pb-c.o": True, "test.so": True}
        timestamps = self._check_file_exists(["a_use.o", "b_notuse.o", "proto/a_proto.pb-c.c", "proto/a_proto.pb-c.h", "proto/a_proto.pb-c.o", "test.so"], check_timestamp=timestamps, is_changed=is_changed)

        umake  = ":foreach proto/*.proto > protoc-c -I={dir} --c_out={dir} {filename} > {dir}/{noext}.pb-c.c {dir}/{noext}.pb-c.h\n"
        umake += ":foreach b_notuse.c > gcc -g -O2 -Wall -fPIC -c {filename} -o {target} > {dir}/{noext}.o\n"
        umake += ": *.o > gcc -g --shared -O2 -Wall -fPIC {filename} -o {target} > test.so\n"
        self._rm(["proto/a_proto.proto", "a_use.c"])
        self._compile(umake)
        self._check_file_not_exists(["proto/a_proto.pb-c.c", "proto/a_proto.pb-c.h", "proto/a_proto.pb-c.o"])
        is_changed = {"b_notuse.o": False, "test.so": True}
        timestamps = self._check_file_exists(["b_notuse.o", "test.so"], check_timestamp=timestamps, is_changed=is_changed)

    def test_recursive_deps(self):
        """ foreach """
        """ for a > b > c > d check if a delete -> all deleted """
        self._create("a", "asd")
        umake = ":foreach a > ../helper_file_create.sh something b > b\n"
        umake += ":foreach b > ../helper_file_create.sh something c > c\n"
        umake += ":foreach c > ../helper_file_create.sh something d > d\n"
        self._compile(umake)
        self._check_file_exists(["a", "b", "c", "d"])
        self._rm(["a"])

        self._compile(umake)
        self._check_file_not_exists(["a", "b", "c", "d"])

        """ for a > b > c > d check if c deleted -> a, b, c, d exists """
        self._create("a", "asd")
        self._compile(umake)
        self._check_file_exists(["a", "b", "c", "d"])
        self._rm(["c"])
        self._compile(umake)
        self._check_file_exists(["a", "b", "c", "d"])

        """ for a > b > c > d check if c deleted -> a, b, c, d exists """
        self._create("a", "asd")
        self._compile(umake)
        self._check_file_exists(["a", "b", "c", "d"])

        umake = ":foreach a > ../helper_file_create.sh something b > b\n"
        umake += ":foreach c > ../helper_file_create.sh something d > d\n"

        self._compile(umake)
        self._check_file_exists(["a", "b"])
        self._check_file_not_exists(["c", "d"])

        """ not foreach  """
        """ for a > b > c > d check if a delete -> all deleted """
        self._create("a", "asd")
        umake = ": a > ../helper_file_create.sh something b > b\n"
        umake += ": b > ../helper_file_create.sh something c > c\n"
        umake += ": c > ../helper_file_create.sh something d > d\n"
        self._compile(umake)
        self._check_file_exists(["a", "b", "c", "d"])

        self._rm(["a"])
        self._compile(umake, should_fail=True)

        """ check if c delete -> all reconstructed """
        self._create("a", "asd")
        self._compile(umake)
        self._check_file_exists(["a", "b", "c", "d"])
        self._rm(["c"])
        self._compile(umake)

        """ if rule b > c delete, should fail, it's considered as wrong UMakefile, no actions is done """
        self._create("a", "asd")
        self._compile(umake)
        self._check_file_exists(["a", "b", "c", "d"])
        umake = ": a > ../helper_file_create.sh something b > b\n"
        umake += ": c > ../helper_file_create.sh something d > d\n"
        self._compile(umake, should_fail=True)
        self._check_file_exists(["a", "b", "c", "d"])
        # self._check_file_not_exists(["c"])

        """ check all sources exists for a command """
        self._create("a", "asd")
        self._create("a1", "asd")
        umake = ": a a1 > ../helper_file_create.sh something b > b\n"
        self._check_file_exists(["b"])
        self._compile(umake)
        self._rm(["a"])
        self._compile(umake, should_fail=True)

        self._create("a", "asd")
        self._compile(umake)

        self._rm(["a1"])
        self._compile(umake, should_fail=True)

        # delete a -> b exists
        # create a -> b exists
        # delete a1 -> b exists

    def test_umakefile_parsing(self):
        umake = "sdfsdf\n"
        self._compile(umake, should_fail=True)

    def test_changing_command_for_target(self):
        """ check that changing command for target play nice """
        self._create("a.c", "")
        self._create("b.c", "")

        umake = ":foreach *.c > gcc -g -O2 -Wall -fPIC -c {filename} -o {target} > {dir}/{noext}.o\n"
        umake += ": *.o > gcc -g --shared -O2 -Wall -fPIC {filename} -o {target} > test.so\n"
        self._compile(umake)
        self._check_file_exists(["a.o", "b.o", "test.so"])

        umake = ": *.c > gcc -g --shared -O2 -Wall -fPIC {filename} -o {target} > test.so\n"
        self._compile(umake)
        self._check_file_exists(["test.so"])
        self._check_file_not_exists(["a.o", "b.o"])

    def test_changing_command_for_target_more_objects(self):
        """ change target and change the number of objects build """
        self._create("a.c", "")
        self._create("b.c", "")
        self._create("c.c", "")

        umake = ":foreach a.c b.c > gcc -g -O2 -Wall -fPIC -c {filename} -o {target} > {dir}/{noext}.o\n"
        umake += ": a.o b.o > gcc -g --shared -O2 -Wall -fPIC {filename} -o {target} > test.so\n"
        self._compile(umake)
        self._check_file_exists(["a.o", "b.o", "test.so"])

        umake = ": a.c b.c c.c > gcc -g --shared -O2 -Wall -fPIC {filename} -o {target} > test.so\n"
        self._compile(umake)
        self._check_file_exists(["test.so"])
        self._check_file_not_exists(["a.o", "b.o"])


    def test_changing_command_for_target_less_objects(self):
        """ check that changing command for target play nice """
        self._create("a.c", "")
        self._create("b.c", "")

        umake = ":foreach *.c > gcc -g -O2 -Wall -fPIC -c {filename} -o {target} > {dir}/{noext}.o\n"
        umake += ": *.o > gcc -g --shared -O2 -Wall -fPIC {filename} -o {target} > test.so\n"
        self._compile(umake)
        self._check_file_exists(["a.o", "b.o", "test.so"])

        umake = ": a.c > gcc -g --shared -O2 -Wall -fPIC {filename} -o {target} > test.so\n"
        self._compile(umake)
        self._check_file_exists(["test.so"])
        self._check_file_not_exists(["a.o", "b.o"])

    def test_change_working_dir(self):
        self._create("other_dir/a.sh", "./b.sh")
        self._create("other_dir/b.sh", "echo 'this is a test' > c")

        umake = "[workdir:other_dir]\n"
        umake += ": > ./a.sh > c\n"
        self._compile(umake)
        self._check_file_exists(["other_dir/c"])

        self._rm(["other_dir/a.sh", "other_dir/b.sh", "other_dir/c"])

        """ check return to root works """
        umake = "[workdir:/]\n"
        umake += ": > ./a.sh > c\n"
        self._compile(umake, should_fail=True)

        """ check absoulute path works """
        self._create("other_dir/a.sh", "./b.sh")
        self._create("other_dir/b.sh", "echo 'this is a test' > ../c")

        umake = "[workdir:other_dir]\n"
        umake += ": > ./a.sh > /c\n"
        self._compile(umake)
        self._check_file_exists(["c"])

    def test_variant(self):
        umake = "[variant:default]\n"
        umake += "$file = a\n"
        umake += "!create(file1) : ../helper_file_create.sh something $file1 > $file1\n"
        umake += ": > !create($file)\n"
        umake += "\n"
        umake += "[variant:test]\n"
        umake += "$file = b\n"
        umake += "!create(file1) : ../helper_file_create.sh something $file1 > $file1\n"
        umake += ": > !create($file)\n"
        umake += "\n"
        self._compile(umake)

        self._check_file_exists(["a"])
        self._check_file_not_exists(["b"])

        self._compile(umake, variant=["test"])
        self._check_file_exists(["b"])
        self._check_file_not_exists(["a"])

        self._compile(umake, variant=["test1"], should_fail=True)

        """ test multiple variants """
        self._compile(umake, variant=["default", "test"])
        self._check_file_exists(["a"])
        self._check_file_exists(["b"])

    def test_compiling_specific_target(self):
        umake = ": > ../helper_file_create.sh something a > a\n"
        umake += ": > ../helper_file_create.sh something b > b\n"
        umake += ": a > ../helper_file_create.sh something c > c\n"
        umake += ": c >  ../helper_file_create.sh something d > d\n"

        timestamps = {"a": 0, "b": 0, "c": 0, "d": 0}
        is_changed = {"a": True, "b": True, "c": True, "d": True}
        self._compile(umake)
        timestamps = self._check_file_exists(["a", "b", "c", "d"], check_timestamp=timestamps, is_changed=is_changed)
        self._rm(["a", "b", "c", "d"])

        timestamps = {"a": 0}
        is_changed = {"a": True}
        self._compile(umake, targets=["a"])
        timestamps = self._check_file_exists(["a"], check_timestamp=timestamps, is_changed=is_changed)
        self._check_file_not_exists(["b", "c", "d"])
        self._compile(umake)
        is_changed = {"a": False, "b": True, "c": True, "d": True}
        timestamps.update({"b": 0, "c": 0, "d": 0})
        self._check_file_exists(["a", "b", "c", "d"], check_timestamp=timestamps, is_changed=is_changed)

        self._rm(["a", "b", "c", "d"])
        self._compile(umake, targets=["d"])
        self._check_file_exists(["a", "c", "d"])
        self._check_file_not_exists(["b"])

        timestamps = {"a": 0, "b": 0, "c": 0, "d": 0}
        is_changed = {"a": True, "b": True, "c": True, "d": True}
        self._compile(umake)
        timestamps = self._check_file_exists(["a", "b", "c", "d"], check_timestamp=timestamps, is_changed=is_changed)

        is_changed = {"a": False, "b": False, "c": False, "d": False}
        self._compile(umake, targets=["d"])
        self._check_file_exists(["a", "b", "c", "d"], check_timestamp=timestamps, is_changed=is_changed)

    def test_autodep_update(self):
        self._create("a", "a")
        self._create("b", "b")
        self._create("d", "d")
        self._create("a.sh", "/bin/cat a && /bin/cat b && echo n >> c\n")
        umake = ": > ./a.sh > c"
        self._compile(umake)
        self._assert_compilation("c", deps_conf=[], deps_manual=[], deps_auto_in=["a", "a.sh", "b"])
        self._create("a.sh", "/bin/cat a && echo n >> c\n")
        self._compile(umake)
        self._assert_compilation("c", deps_conf=[], deps_manual=[], deps_auto_in=["a", "a.sh"])

        self._create("a.sh", "/bin/cat a && /bin/cat d && /bin/cat b && echo n >> c\n")
        self._compile(umake)
        self._assert_compilation("c", deps_conf=[], deps_manual=[], deps_auto_in=["a", "a.sh", "b", "d"])

    def test_include(self):
        self._create("UMakfile_b", ": > ../helper_file_create.sh something b > b\n")
        umake = "[include:UMakfile_b]\n"
        self._compile(umake)

        self._create("other_dir/a", "")
        self._create("other_dir/a.sh", "/bin/cat a && echo n >> b")
        self._create("other_dir/UMakefile", ": a > ./a.sh > b\n")

        umake = "[workdir:other_dir]\n"
        umake += "[include:UMakefile]\n"
        self._compile(umake)
        self._check_file_exists(["other_dir/b"])

    def test_clean_exit(self):
        # Create two parallel targets that are not related.
        # This should make umake trigger two workers to handle the commands.
        # The first command will fail and we want to make sure that all workers
        # are terminated.
        umake = ": > /bin/sleep 0.5 && false > \n"
        umake += ": > /bin/sleep 60 > \n"
        start = time.perf_counter()
        self._compile(umake, should_fail=True)
        assert time.perf_counter() - start < 5

    def test_benchmark(self):
        n_files = 300
        umake = ""
        for i in range(n_files):
            self._create(f"{i}.c",
f"""
int x{i};
int my_func{i}()
{{
    x{i}++;
    return 0;
}}
""")
            umake += f": {i}.c > gcc -g -O2 -Wall -fPIC -c {{filename}} -o {{target}} > {i}.o\n"
        
        with Timer("build", n_files):
            self._compile(umake, should_output=False, local_cache=True)
        
        with Timer("build - null", n_files):
            self._compile(umake, should_output=False, local_cache=True)
        os.remove("env/.umake/db.pickle")
        with Timer("build - from local cache", n_files):
            self._compile(umake, should_output=False, local_cache=True)

    BUCKET_NAME = "umake-bucket"
    def _start_remote_cache_minio(self):
        os.environ["MINIO_ACCESS_KEY"] = "umake"
        os.environ["MINIO_SECRET_KEY"] = "umakeumake"
        cmd = "minio server /data"
        server = Popen(cmd, shell=True)
        time.sleep(4)
        self.mc = Minio("0.0.0.0:9000",access_key="umake", secret_key="umakeumake", secure=False)
        try:
            for obj in self.mc.list_objects(bucket_name=self.BUCKET_NAME, recursive=True):
                self.mc.remove_object(bucket_name=self.BUCKET_NAME, object_name=obj.object_name)
            self.mc.remove_bucket(self.BUCKET_NAME)
        except minio.error.NoSuchBucket:
            pass
            
        self.mc.make_bucket(self.BUCKET_NAME)
        return server

    def test_remote_cache(self):
        minio_server = self._start_remote_cache_minio()
        umake = f"[remote_cache:minio 0.0.0.0:9000 umake umakeumake {self.BUCKET_NAME} rw]\n"
        umake += ": > touch f > f"
        self._compile(umake, remote_cache=True)

        self.mc.stat_object(self.BUCKET_NAME, "md-48b67e8fe03dc99f08de9753e3a1dae34eb0b136")
        self.mc.remove_object(self.BUCKET_NAME, "md-48b67e8fe03dc99f08de9753e3a1dae34eb0b136")
        self._rm(["f"])
        """ test env"""
        os.environ["UMAKE_CONFIG_REMOTE_CACHE"] = f"minio 0.0.0.0:9000 umake umakeumake {self.BUCKET_NAME} rw"
        umake = ": > touch f > f"
        
        self._compile(umake, remote_cache=True)

        self.mc.stat_object(self.BUCKET_NAME, "md-48b67e8fe03dc99f08de9753e3a1dae34eb0b136")
        self.mc.remove_object(self.BUCKET_NAME, "md-48b67e8fe03dc99f08de9753e3a1dae34eb0b136")
        self._rm(["f"])
        del os.environ["UMAKE_CONFIG_REMOTE_CACHE"]

        """ read only """
        umake = f"[remote_cache:minio 0.0.0.0:9000 umake umakeumake {self.BUCKET_NAME} ro]\n"
        umake += ": > touch f > f"
        self._compile(umake, remote_cache=True)

        with self.assertRaises(minio.error.NoSuchKey) as context:
            self.mc.stat_object(self.BUCKET_NAME, "md-48b67e8fe03dc99f08de9753e3a1dae34eb0b136")

        """ no remote cache """
        self.mc.remove_object(self.BUCKET_NAME, "md-48b67e8fe03dc99f08de9753e3a1dae34eb0b136")
        self._rm(["f"])
        umake = ": > touch f > f"

        with self.assertRaises(minio.error.NoSuchKey) as context:
            self.mc.stat_object(self.BUCKET_NAME, "md-48b67e8fe03dc99f08de9753e3a1dae34eb0b136")

        minio_server.terminate()

    def test_local_cache(self):
        umake = f"[local_cache_size:100]\n"
        umake += ": > touch f > f"
        self._compile(umake, local_cache=True)
        assert os.path.exists("env/.umake/build-cache/md-48b67e8fe03dc99f08de9753e3a1dae34eb0b136") == True

        umake = f"[local_cache_size:0]\n"
        umake += ": > touch f > f"
        self._compile(umake, local_cache=True)
        assert os.path.exists("env/.umake/build-cache/md-48b67e8fe03dc99f08de9753e3a1dae34eb0b136") == False


if __name__ == '__main__':
    unittest.main()
