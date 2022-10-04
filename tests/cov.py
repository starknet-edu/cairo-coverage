from collections import defaultdict
from dataclasses import dataclass
from os import get_terminal_size
from textwrap import wrap
from typing import Any, Dict, Optional, Set

from starkware.cairo.lang.compiler.program import ProgramBase
from starkware.cairo.lang.vm import cairo_runner
from starkware.cairo.lang.vm.builtin_runner import BuiltinRunner
from starkware.cairo.lang.vm.relocatable import MaybeRelocatable
from starkware.cairo.lang.vm.vm_core import RunContext, VirtualMachine


class Headers:
    FILE: str = "File "
    FILE_INDEX: int = 0

    COVERED: str = "Covered(%) "
    COVERED_INDEX: int = 1

    MISSED: str = "Missed(%) "
    MISSED_INDEX: int = 2

    LINES_MISSED: str = "Lines missed"
    LINE_MISSED_INDEX: int = 3


class Colors:
    FAIL = "\033[91m"
    GREEN = "\033[92m"
    WARNING = "\033[93m"
    END = "\033[0m"


@dataclass
class CoverageFile:
    name: str
    covered: Set[int]
    statements: Set[int]
    precision: int = 1

    @staticmethod
    def col_sizes(sizes=[]):
        return sizes

    def __post_init__(self):
        self.nb_statements = len(self.statements)
        self.nb_covered = len(self.covered)
        self.missed = sorted(list(self.statements - self.covered))
        self.nb_missed = len(self.missed)
        self.pct_covered = 100 * self.nb_covered / self.nb_statements
        self.pct_missed = 100 * self.nb_missed / self.nb_statements

    def __str__(self):
        sizes = self.__class__.col_sizes()
        name_len = len(self.name)
        if name_len > sizes[Headers.FILE_INDEX]:
            name = f"{f'[...]{self.name[5 + name_len - sizes[Headers.FILE_INDEX]:]}':<{sizes[Headers.FILE_INDEX]}}"
        else:
            name = f"{self.name:<{sizes[Headers.FILE_INDEX]}}"
        pct_covered = f"{self.pct_covered:<{sizes[Headers.COVERED_INDEX]}.{self.precision}f}"
        pct_missed = f"{self.pct_missed:<{sizes[Headers.MISSED_INDEX]}.{self.precision}f}"
        prefix = " " * (len(name) + len(pct_covered) + len(pct_missed) + 5)
        missed = wrap(str(self.missed), sizes[Headers.LINE_MISSED_INDEX], initial_indent=" ")
        missed[1:] = [f"{prefix}{val}" for val in missed[1:]]
        missed = "\n".join(missed)
        if 0 <= self.pct_covered < 50:
            color = Colors.FAIL
        elif 50 <= self.pct_covered < 80:
            color = Colors.WARNING
        else:
            color = Colors.GREEN
        return f"{color}{name} {pct_covered} {pct_missed} {missed}{Colors.END}"


def print_sum(covered_files: CoverageFile):
    max_name = max([len(file.name) for file in covered_files]) + 2
    max_missed_lines = max([len(str(file.missed)) for file in covered_files])
    sizes = CoverageFile.col_sizes()
    sizes.extend([max_name, len(Headers.COVERED), len(Headers.MISSED), max_missed_lines])
    term_size = get_terminal_size()
    while sum(sizes) > term_size.columns:
        idx = sizes.index(max(sizes))
        sizes[idx] = int(0.75 * sizes[idx])

    headers = (
        f"\n{Headers.FILE:{sizes[Headers.FILE_INDEX] + 1}}"
        f"{Headers.COVERED:{sizes[Headers.COVERED_INDEX] + 1}}"
        f"{Headers.MISSED:{sizes[Headers.MISSED_INDEX] + 1}}"
        f"{Headers.LINES_MISSED:{sizes[Headers.LINE_MISSED_INDEX] + 1}}\n"
    )
    underline = "-" * len(headers)
    print(headers + underline)
    for file in covered_files:
        print(file)


def report_runs(excluded_file: Optional[Set[str]] = None, out_file: Optional[str] = None, print_summary: bool = True):
    if excluded_file is None:
        excluded_file = []
    assert out_file is None or out_file.endswith(".json"), "Only json supported for now"
    report_dict = OverrideVm.covered()
    statements = OverrideVm.statements()
    files = sorted(
        [
            CoverageFile(statements=set(statements[file]), covered=set(coverage), name=file)
            for file, coverage in report_dict.items()
            if file not in excluded_file
        ],
        key=lambda x: x.name,
    )

    if print_summary:
        print_sum(covered_files=files)


class OverrideVm(VirtualMachine):
    def __init__(
        self,
        program: ProgramBase,
        run_context: RunContext,
        hint_locals: Dict[str, Any],
        static_locals: Optional[Dict[str, Any]] = None,
        builtin_runners: Optional[Dict[str, BuiltinRunner]] = None,
        program_base: Optional[MaybeRelocatable] = None,
    ):
        super().__init__(
            program=program,
            run_context=run_context,
            hint_locals=hint_locals,
            static_locals=static_locals,
            builtin_runners=builtin_runners,
            program_base=program_base,
        )
        self.old_end_run = super().end_run

    def touched_pcs(self):
        return set(trace_entry.pc.offset for trace_entry in self.trace)

    def end_run(self):
        self.old_end_run()
        if self.program.debug_info is not None:
            self.pcs = self.touched_pcs()
            self.cover_file()

    @staticmethod
    def covered(val: defaultdict(list) = defaultdict(list)):
        return val

    @staticmethod
    def statements(val: defaultdict(list) = defaultdict(list)):
        return val

    def pc_to_line(
        self,
        pc,
        statements: defaultdict(list),
        report_dict: defaultdict(list) = None,
    ) -> None:
        should_update_report = pc in self.pcs
        instruct = self.program.debug_info.instruction_locations[pc].inst
        file = instruct.input_file.filename
        while True:
            if "autogen" not in file:
                lines = list(
                    range(
                        instruct.start_line,
                        instruct.end_line + 1,
                    )
                )
                if should_update_report:
                    report_dict[file].extend(lines)
                statements[file].extend(lines)
            if instruct.parent_location is not None:
                instruct = instruct.parent_location[0]
                file = instruct.input_file.filename
            else:
                return

    def cover_file(
        self,
    ):
        report_dict = self.__class__.covered()
        statements = self.__class__.statements()
        for pc in set(self.program.debug_info.instruction_locations.keys()):
            self.pc_to_line(pc=pc, report_dict=report_dict, statements=statements)


cairo_runner.VirtualMachine = OverrideVm
