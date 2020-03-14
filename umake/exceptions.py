class TargetNotGeneratedErr(Exception):
    pass


class CompilationFailedErr(Exception):
    pass


class CmdFailedErr(Exception):
    pass


class NotFileErr(Exception):
    pass


class DepIsGenerated(Exception):
    pass


class LineParseErr(Exception):
    pass


class CleanExitErr(Exception):
    pass