from os import path

from asynctest import TestCase
from pytest import mark
from starkware.starknet.testing.contract_utils import get_contract_class
from starkware.starknet.testing.starknet import Starknet

from cairo_coverage import cairo_coverage

CONTRACT_FILE = path.join("examples", "contracts", "array.cairo")
PRODUCT_ARRAY = [(x, x + 1) for x in range(1, 6, 2)]


class CairoContractTest(TestCase):
    @classmethod
    async def setUp(cls):
        cairo_coverage.reset()
        cls.starknet = await Starknet.empty()

        cls.contract = await cls.starknet.deploy(
            contract_class=get_contract_class(source=CONTRACT_FILE, disable_hint_validation=True),
            disable_hint_validation=True,
        )

    @mark.asyncio
    async def test_array_contract(self):
        res = await self.contract.view_product(array=PRODUCT_ARRAY).call()
        cairo_coverage.report_runs()
