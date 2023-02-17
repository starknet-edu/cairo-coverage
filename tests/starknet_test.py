import os

import pytest
import pytest_asyncio

from starkware.starknet.testing.contract import StarknetContract
from starkware.starknet.testing.starknet import Starknet
from starkware.starknet.compiler.compile import compile_starknet_files

from cairo_coverage import cairo_coverage

CONTRACT_FILE = os.path.join(os.path.dirname(__file__), "test.cairo")


@pytest_asyncio.fixture
async def starknet() -> Starknet:
    return await Starknet.empty()


@pytest_asyncio.fixture
async def contract(starknet: Starknet) -> StarknetContract:
    return await starknet.deploy(source=CONTRACT_FILE)


@pytest.mark.asyncio
async def test_cover_constructor():
    cairo_coverage.reset()
    assert cairo_coverage.report_runs(print_summary=False) == []


@pytest.mark.asyncio
async def test_l2_to_l1_message(contract: StarknetContract):

    l1_address = int("0xce08635cc6477f3634551db7613cc4f36b4e49dc", 16)
    payload = [6, 28]

    cairo_coverage.reset()

    await contract.send_message(to_address=l1_address, payload=payload).execute()
    coverage = cairo_coverage.report_runs(print_summary=False)
    coverage_file = [file for file in coverage if file.name.endswith("tests/test.cairo")].pop()

    assert coverage_file.covered == set(range(61, 64))


@pytest.mark.asyncio
async def test_l1_to_l2_message(starknet: Starknet, contract: StarknetContract):
    l1_address = int("0xce08635cc6477f3634551db7613cc4f36b4e49dc", 16)
    user = 6
    amount = 28

    cairo_coverage.reset()

    # Send message to L2: Deposit 28 to user 6.
    await starknet.send_message_to_l2(
        from_address=l1_address,
        to_address=contract.contract_address,
        selector="deposit",
        payload=[user, amount],
    )

    coverage = cairo_coverage.report_runs(print_summary=False)
    coverage_file = [file for file in coverage if file.name.endswith("tests/test.cairo")].pop()
    deposit_lines = set(range(67, 70))
    increase_value_lines = set(range(21, 24))
    assert coverage_file.covered == deposit_lines.union(increase_value_lines)


@pytest.mark.asyncio
async def test_contract_interaction(starknet: Starknet):
    contract_class = compile_starknet_files([CONTRACT_FILE], debug_info=True)
    contract = await starknet.deploy(contract_class=contract_class)
    proxy_contract = await starknet.deploy(contract_class=contract_class)

    cairo_coverage.reset()

    await proxy_contract.call_increase_value(contract.contract_address, 123, 234).execute()
    assert (await proxy_contract.get_value(123).execute()).result == (0,)
    assert (await contract.get_value(123).execute()).result == (234,)
    coverage = cairo_coverage.report_runs(print_summary=False)
    coverage_file = [file for file in coverage if file.name.endswith("tests/test.cairo")].pop()
    call_increase_value_lines = set(range(27, 32))
    interface_line = {16}
    increase_value_lines = set(range(21, 24))
    get_value_lines = set(range(35, 38))
    skipped_empty_line = 29
    call_increase_value_lines.remove(skipped_empty_line)

    assert coverage_file.covered == call_increase_value_lines.union(
        interface_line.union(increase_value_lines.union(get_value_lines))
    )


@pytest.mark.asyncio
async def test_struct_arrays(starknet: Starknet):
    contract_class = compile_starknet_files([CONTRACT_FILE], debug_info=True)

    cairo_coverage.reset()

    contract = await starknet.deploy(contract_class=contract_class)
    assert (await contract.transpose([(123, 234), (4, 5)]).execute()).result == (
        [
            contract.Point(x=123, y=4),
            contract.Point(x=234, y=5),
        ],
    )
    transpose_lines = set(range(103, 109))
    coverage = cairo_coverage.report_runs(print_summary=False)
    coverage_file = [file for file in coverage if file.name.endswith("tests/test.cairo")].pop()
    assert coverage_file.covered == transpose_lines
