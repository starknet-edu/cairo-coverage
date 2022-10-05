from collections import defaultdict
from dataclasses import dataclass
from os import get_terminal_size
from textwrap import wrap
from typing import Any, Dict, List, Optional, Set

from starkware.cairo.lang.compiler.program import ProgramBase
from starkware.cairo.lang.vm import cairo_runner
from starkware.cairo.lang.vm.builtin_runner import BuiltinRunner
from starkware.cairo.lang.vm.relocatable import MaybeRelocatable
from starkware.cairo.lang.vm.vm_core import RunContext, VirtualMachine


class Headers:
    """Headers for the report table."""

    FILE: str = "File "
    FILE_INDEX: int = 0

    COVERED: str = "Covered(%) "
    COVERED_INDEX: int = 1

    MISSED: str = "Missed(%) "
    MISSED_INDEX: int = 2

    LINES_MISSED: str = "Lines missed"
    LINE_MISSED_INDEX: int = 3


class Colors:
    """Colors to indicate if the coverage is good or not."""

    FAIL = "\033[91m"
    GREEN = "\033[92m"
    WARNING = "\033[93m"
    END = "\033[0m"


@dataclass
class CoverageFile:
    name: str  # filename
    covered: Set[int]  # tested lines
    statements: Set[int]  # lines with code
    precision: int = 1  # decimals for %

    @staticmethod
    def col_sizes(sizes=[]):
        """To share the column sizes between all the instances."""
        return sizes

    def __post_init__(self):
        self.nb_statements = len(
            self.statements
        )  # nb of lines with code in the cairo file
        self.nb_covered = len(self.covered)  # nb of lines tested
        self.missed = sorted(list(self.statements - self.covered))  # lines not tested
        self.nb_missed = len(self.missed)  # nb of lines not tested
        self.pct_covered = (
            100 * self.nb_covered / self.nb_statements
        )  # % of lines tested
        self.pct_missed = (
            100 * self.nb_missed / self.nb_statements
        )  # % of lines not tested

    def __str__(self):
        sizes = self.__class__.col_sizes()  # get columns size
        name_len = len(self.name)
        if (
            name_len > sizes[Headers.FILE_INDEX]
        ):  # if the filename is longer than the col len we crop it
            name = f"{'[...]' + self.name[5 + name_len - sizes[Headers.FILE_INDEX]:]:<{sizes[Headers.FILE_INDEX]}}"
            # self.name[5 + name_len - sizes[Headers.FILE_INDEX] crops the filename so it fits in the column
            # :<{sizes[Headers.FILE_INDEX] formats the string to be left centered and pads it to the column length
        else:
            name = f"{self.name:<{sizes[Headers.FILE_INDEX]}}"  # pads the filename to the column length
        pct_covered = f"{self.pct_covered:^{sizes[Headers.COVERED_INDEX]}.{self.precision}f}"  # % covered centered with right decimals
        pct_missed = f"{self.pct_missed:^{sizes[Headers.MISSED_INDEX]}.{self.precision}f}"  # % missed centered with right decimals
        prefix = " " * (
            len(name) + len(pct_covered) + len(pct_missed) + 5
        )  # offset of the missed lines column
        missed = wrap(
            str(self.missed), sizes[Headers.LINE_MISSED_INDEX], initial_indent=" "
        )  # wrap the missed lines list if too big
        missed[1:] = [
            f"{prefix}{val}" for val in missed[1:]
        ]  # prefix the wrapped missed lines
        missed = "\n".join(missed)  # convert it to multiline string
        if 0 <= self.pct_covered < 50:  # if coverage is not enough writes in red
            color = Colors.FAIL
        elif 50 <= self.pct_covered < 80:  # if coverage is mid enough writes in yellow
            color = Colors.WARNING
        else:  # if coverage is good write in green
            color = Colors.GREEN
        return f"{color}{name} {pct_covered} {pct_missed} {missed}{Colors.END}"  # formatted file line report


def print_sum(covered_files: CoverageFile):
    """Print the coverage summary of the project."""
    try:
        term_size = get_terminal_size()
        max_name = max([len(file.name) for file in covered_files]) + 2  # longest name
        max_missed_lines = max(
            [len(str(file.missed)) for file in covered_files]
        )  # length of the longest missed lines list
        sizes = (
            CoverageFile.col_sizes()
        )  # init the sizes list with our static method so it's available everywhere
        sizes.extend(
            [max_name, len(Headers.COVERED), len(Headers.MISSED), max_missed_lines]
        )  # fill the sizes
        while (
            sum(sizes) > term_size.columns
        ):  # while the length of all the cols is > the terminal size, reduce the biggest col
            idx = sizes.index(max(sizes))
            sizes[idx] = int(0.75 * sizes[idx])

        headers = (  # prepare the coverage table headers
            f"\n{Headers.FILE:{sizes[Headers.FILE_INDEX] + 1}}"
            f"{Headers.COVERED:{sizes[Headers.COVERED_INDEX] + 1}}"
            f"{Headers.MISSED:{sizes[Headers.MISSED_INDEX] + 1}}"
            f"{Headers.LINES_MISSED:{sizes[Headers.LINE_MISSED_INDEX] + 1}}\n"
        )
        underline = "-" * len(headers)  # to separate the header from the values
        print(headers + underline)
        for file in covered_files:  # prints the report of each file
            print(file)
    except OSError:
        pass


def report_runs(
    excluded_file: Optional[Set[str]] = None,
    print_summary: bool = True,
):
    if excluded_file is None:
        excluded_file = []
    report_dict = OverrideVm.covered()  # get the infos of all the covered files
    statements = OverrideVm.statements()  # get the lines of codes of each files
    files = sorted(  # sort the files by filename
        [
            CoverageFile(
                statements=set(statements[file]), covered=set(coverage), name=file
            )
            for file, coverage in report_dict.items()
            if file not in excluded_file
        ],
        key=lambda x: x.name,
    )

    if not len(files):
        print("Nothing to report")
        return "Nothing to report"
    if print_summary:
        print_sum(covered_files=files)
    return files

def reset():
    OverrideVm.covered().clear()
    OverrideVm.statements().clear()
    CoverageFile.col_sizes().clear()


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
        self.old_end_run = (
            super().end_run
        )  # save the old end run function to wrap it afterwards
        self.old_run_instruction = (
            super().run_instruction
        )  # save the old run instruction function to wrap it afterwards
        self.old_as_vm_exception = (
            super().as_vm_exception
        )  # save the old vm as exception function to wrap it afterwards
        self.touched_pcs = []

    def run_instruction(self, instruction):
        """Saves the current pc and runs the instruction."""
        self.touched_pcs.append(self.run_context.pc.offset)
        self.old_run_instruction(instruction=instruction)

    def end_run(self):
        """In case the run doesn't fail creates report coverage."""
        self.old_end_run()
        self.cover_file()

    def as_vm_exception(
        self,
        exc,
        with_traceback: bool = True,
        notes: Optional[List[str]] = None,
        hint_index: Optional[int] = None,
    ):
        """In case the run fails creates report coverage."""
        self.cover_file()
        return self.old_as_vm_exception(exc, with_traceback, notes, hint_index)

    @staticmethod
    def covered(val: defaultdict(list) = defaultdict(list)) -> defaultdict(list):
        """To share the covered files between all the instances."""
        return val

    @staticmethod
    def statements(val: defaultdict(list) = defaultdict(list)) -> defaultdict(list):
        """To share the lines of codes in files between all the instances."""
        return val

    def pc_to_line(
        self,
        pc,
        statements: defaultdict(list),
        report_dict: defaultdict(list) = None,
    ) -> None:
        """Converts the touched pcs to the line numbers of the original file and saves them."""
        should_update_report = (
            pc in self.touched_pcs
        )  # If the pc is not touched by the test don't report it
        instruct = self.program.debug_info.instruction_locations[
            pc
        ].inst  # first instruction in the debug info
        file = instruct.input_file.filename  # current analyzed file
        while True:
            if "autogen" not in file:  # if file is auto generated discard it
                lines = list(  # get the lines touched
                    range(
                        instruct.start_line,
                        instruct.end_line + 1,
                    )
                )
                if should_update_report:
                    report_dict[file].extend(lines)
                statements[file].extend(lines)
            if (
                instruct.parent_location is not None
            ):  # continue until we have last parent location
                instruct = instruct.parent_location[0]
                file = instruct.input_file.filename
            else:
                return

    def cover_file(
        self,
    ):
        """Adds the coverage report in the report dict and all the lines of code."""
        if self.program.debug_info is not None:
            report_dict = self.__class__.covered()
            statements = self.__class__.statements()
            for pc in set(self.program.debug_info.instruction_locations.keys()):
                self.pc_to_line(pc=pc, report_dict=report_dict, statements=statements)


cairo_runner.VirtualMachine = OverrideVm
