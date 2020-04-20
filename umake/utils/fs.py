import os
from subprocess import check_output, CalledProcessError
from umake.config import ROOT

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


def join_paths(root, rest):
    if rest[0] == "/":
        ret = f"{ROOT}/{rest[1:]}"
    else:
        ret = f"{root}/{rest}"
    return ret


def get_size_KB(path):
    try:
        return int(check_output(['du','-s', path]).split()[0].decode('utf-8'))
    except CalledProcessError:
        return 0