from collections import defaultdict
from json import dump
from sys import stdout
from typing import Any, Dict, Optional


from starkware.cairo.lang.compiler.program import ProgramBase
from starkware.cairo.lang.vm.relocatable import MaybeRelocatable
from starkware.cairo.lang.vm.vm_core import RunContext
from starkware.cairo.lang.vm.builtin_runner import BuiltinRunner
from starkware.cairo.lang.vm.vm_core import VirtualMachine

from coverage.results import Numbers


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
            self.report()

    @staticmethod
    def covered(val: defaultdict(list) = defaultdict(list)):
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

    def report(
        self,
    ):
        print()
        report_dict = self.__class__.covered()
        statements = defaultdict(list)
        for pc in set(self.program.debug_info.instruction_locations.keys()):
            self.pc_to_line(pc=pc, report_dict=report_dict, statements=statements)
        report_file = {}
        pr_dict = {}
        for file, coverage in report_dict.items():
            n_statements = len(set(statements[file]))
            n_executed = len(set(coverage))
            n_missing = n_statements - n_executed
            num = Numbers(
                precision=1,
                n_files=len(report_dict.keys()),
                n_statements=n_statements,
                n_excluded=0,
                n_missing=n_missing,
                n_branches=0,
                n_partial_branches=0,
                n_missing_branches=0,
            )
            pr_dict[file] = num
            report_file[file] = self.report_one_file(nums=num, executed=coverage)
        self.print_sum(pr_dict)

        with open("report.json", "w") as f:
            dump(report_file, f, sort_keys=True, indent=4)

    def print_sum(self, pr_dict):
        max_name = max([len(filenames) for filenames in pr_dict] + [5])
        fmt_name = "%%- %ds  " % max_name
        fmt_skip_covered = "\n%s file%s skipped due to complete coverage."
        fmt_skip_empty = "\n%s empty file%s skipped."

        header = (fmt_name % "Name") + " Stmts   Miss"
        fmt_coverage = fmt_name + "%6d %6d"
        width100 = Numbers(precision=1).pc_str_width()
        header += "%*s" % (width100 + 4, "Cover")
        fmt_coverage += "%%%ds%%%%" % (width100 + 3,)

        header += "   Missing"
        fmt_coverage += "   %s"
        rule = "-" * len(header)

        column_order = dict(name=0, stmts=1, miss=2, cover=-1)
        lines = []

        self.writeout(header)
        self.writeout(rule)
        for file, nums in pr_dict.items():
            args = (file, nums.n_statements, nums.n_missing, nums.pc_covered_str, 100 - float(nums.pc_covered_str))
            text = fmt_coverage % args
            # Add numeric percent coverage so that sorting makes sense.
            args += (nums.pc_covered,)
            lines.append((text, args))
        for line in lines:
            self.writeout(line[0])

    def report_one_file(self, nums, executed):
        """Extract the relevant report data for a single file."""
        summary = {
            "covered_lines": nums.n_executed,
            "num_statements": nums.n_statements,
            "percent_covered": nums.pc_covered,
            "percent_covered_display": nums.pc_covered_str,
            "missing_lines": nums.n_missing,
            "excluded_lines": nums.n_excluded,
        }
        reported_file = {
            "executed_lines": sorted(list(set(executed))),
            "summary": summary,
            "missing_lines": [],
            "excluded_lines": [],
        }
        return reported_file

    def writeout(self, line):
        """Write a line to the output, adding a newline."""
        stdout.write(line.rstrip())
        stdout.write("\n")
