from umake.colored_output import format_text, out, bcolors
import time

class Timer:
    def __init__(self, msg, threshold=0, color=bcolors.OKGREEN):
        self.msg = msg
        self.postfix = ""
        self.prefix = ""
        self.threshold = threshold
        self.color = color
        self.log_lines = list()

    def set_prefix(self, prefix):
        self.prefix = prefix

    def set_postfix(self, postfix):
        self.postfix = postfix

    def add_log_line(self, msg):
        self.log_lines.append(msg)

    def __enter__(self):
        self.start = time.time()
        return self

    def __exit__(self, *args):
        self.end = time.time()
        self.interval = self.end - self.start
        out_str = ""
        if self.interval > self.threshold:
            out_str += format_text(f"[{self.interval:.3f}] {self.prefix} {self.msg} {self.postfix}", self.color)
        if self.log_lines:
            if out_str:
                out_str += "\n"
            out_str += "\n".join(self.log_lines)
        if out_str:
            out.print_neutarl(out_str)
