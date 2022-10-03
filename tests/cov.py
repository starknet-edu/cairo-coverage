from collections import defaultdict
from dataclasses import dataclass
from json import dump
from typing import Any, Dict, Optional, Set

from colorama import Fore, Style
from columnar import columnar
from starkware.cairo.lang.compiler.program import ProgramBase
from starkware.cairo.lang.vm.builtin_runner import BuiltinRunner
from starkware.cairo.lang.vm.relocatable import MaybeRelocatable
from starkware.cairo.lang.vm.vm_core import RunContext, VirtualMachine
from starkware.cairo.lang.vm import cairo_runner


@dataclass
class CoverageFile:
    name: str
    covered: Set[int]
    statements: Set[int]
    precision: int = 1

    def __post_init__(self):
        self.nb_statements = len(self.statements)
        self.nb_covered = len(self.covered)
        self.missed = sorted(list(self.statements - self.covered))
        self.nb_missed = len(self.missed)
        self.pct_covered = 100 * self.nb_covered / self.nb_statements
        self.pct_missed = 100 * self.nb_missed / self.nb_statements

    def columnar_format(self):
        missed = "" if not self.missed else self.missed
        if self.pct_covered < 50.0:
            color = Fore.RED
        elif 50.0 <= self.pct_covered < 80.0:
            color = Fore.YELLOW
        else:
            color = Fore.GREEN
        return [
            f"{color}{self.name}  {Style.RESET_ALL}",
            f"{color}{self.nb_statements}{Style.RESET_ALL}",
            f"{color}{self.pct_covered:.{self.precision}f}{Style.RESET_ALL}",
            f"{color}{self.pct_missed:.{self.precision}f}{Style.RESET_ALL}",
            f"{color}{missed}{Style.RESET_ALL}",
        ]


def report_runs(
    excluded_file: Optional[Set[str]] = None, precision=1, out_file: Optional[str] = None, print_summary: bool = True
):
    if excluded_file is None:
        excluded_file = []
    assert out_file.endswith(".json"), "Only json supported for now"
    report_dict = OverrideVm.covered()
    statements = OverrideVm.statements()
    report_file = {}
    print()
    files = [
        CoverageFile(statements=set(statements[file]), covered=set(coverage), name=file, precision=precision)
        for file, coverage in report_dict.items()
        if file not in excluded_file
    ]

    if out_file is not None:
        for file in files:
            report_one_file(covered_file=file)
    if print_summary:
        print(
            columnar(
                data=[x.columnar_format() for x in files],
                headers=["  Name  ", "  Statements  ", "  Covered  ", "  Missed  ", "  Missing lines  "],
                justify=["l", "c", "c", "c", "l"],
            )
        )

    with open(out_file, "w") as f:
        dump(report_file, f, sort_keys=True, indent=4)


def report_one_file(covered_file: CoverageFile):
    """Extract the relevant report data for a single file."""
    summary = {
        "covered_lines": covered_file.nb_covered,
        "num_statements": covered_file.nb_statements,
        "percent_covered": covered_file.pct_covered,
        "missing_lines": covered_file.nb_missed,
        "excluded_lines": 0,
    }
    reported_file = {
        "executed_lines": covered_file.covered,
        "summary": summary,
        "missing_lines": [],
        "excluded_lines": [],
    }
    return reported_file


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
