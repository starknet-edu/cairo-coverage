import os
from typing import Dict
import pytest
from asynctest import TestCase
from starkware.starknet.testing.starknet import Starknet
from starkware.starknet.testing.contract_utils import get_contract_class
from coverage.results import Numbers
from starkware.cairo.lang.vm.vm_core import VirtualMachine
import json
from starkware.cairo.lang.vm.trace_entry import TraceEntry
from collections import defaultdict

CONTRACT_FILE = os.path.join("contracts", "array.cairo")
PRODUCT_ARRAY = [(x, x + 1) for x in range(1, 6, 2)]
coverage_pcs = []


def pc_to_line(compiled, pc, report_dict) -> Dict[str, list]:
    if pc in compiled.program.debug_info.instruction_locations:
        instruct = compiled.program.debug_info.instruction_locations[pc].inst
        file = instruct.input_file.filename
        while True:
            report_dict[file].extend(
                list(
                    range(
                        instruct.start_line,
                        instruct.start_line + 1,
                    )
                )
            )
            instruct = (
                instruct.parent_location[0]
                if instruct.parent_location is not None
                else None
            )
            if instruct is None:
                return report_dict
            file = instruct.input_file.filename
    else:
        return report_dict


def run_instruction(self, instruction):
    try:
        # Compute operands.
        operands, operands_mem_addresses = self.compute_operands(instruction)
    except Exception as exc:
        raise self.as_vm_exception(exc) from None

    try:
        # Opcode assertions.
        self.opcode_assertions(instruction, operands)
    except Exception as exc:
        raise self.as_vm_exception(exc) from None

    # Write to trace.
    self.trace.append(
        TraceEntry(
            pc=self.run_context.pc,
            ap=self.run_context.ap,
            fp=self.run_context.fp,
        )
    )

    global coverage_pcs
    coverage_pcs.append(self.run_context.pc.offset)

    self.accessed_addresses.update(operands_mem_addresses)
    self.accessed_addresses.add(self.run_context.pc)

    try:
        # Update registers.
        self.update_registers(instruction, operands)
    except Exception as exc:
        raise self.as_vm_exception(exc) from None

    self.current_step += 1


VirtualMachine.run_instruction = run_instruction


def report_one_file(nums, executed):
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


class CairoContractTest(TestCase):
    @classmethod
    async def setUp(cls):
        cls.starknet = await Starknet.empty()
        global compiled_contract
        compiled_contract = get_contract_class(
            source=CONTRACT_FILE, disable_hint_validation=True
        )

        cls.contract = await cls.starknet.deploy(
            contract_class=compiled_contract, disable_hint_validation=True
        )

    @pytest.mark.asyncio
    async def test_array_contract(self):
        global coverage_pcs
        coverage_pcs = []
        res = await self.contract.view_product(array=PRODUCT_ARRAY).call()
        report_dict = defaultdict(list)
        for pc in coverage_pcs:
            covered = pc_to_line(compiled_contract, pc, report_dict)
        statements = defaultdict(list)
        for pc in list(
            compiled_contract.program.debug_info.instruction_locations.keys()
        ):
            pc_to_line(
                compiled_contract,
                pc,
                statements,
            )
        report_file = dict()
        for file, coverage in covered.items():
            n_statements = len(set(statements[file]))
            n_executed = len(set(coverage))
            n_missing = n_statements - n_executed
            num = Numbers(
                precision=3,
                n_files=len(covered.keys()),
                n_statements=n_statements,
                n_excluded=0,
                n_missing=n_missing,
                n_branches=0,
                n_partial_branches=0,
                n_missing_branches=0,
            )
            report_file[file] = report_one_file(nums=num, executed=coverage)
        with open("report.json", "w") as f:
            json.dump(report_file, f, sort_keys=True, indent=4)
