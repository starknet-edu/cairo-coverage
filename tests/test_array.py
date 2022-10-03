from os import path

from asynctest import TestCase
from pytest import mark
from starkware.cairo.lang.vm import cairo_runner
from starkware.starknet.testing.contract_utils import get_contract_class
from starkware.starknet.testing.starknet import Starknet

from tests import cov

CONTRACT_FILE = path.join("contracts", "array.cairo")
PRODUCT_ARRAY = [(x, x + 1) for x in range(1, 6, 2)]

cairo_runner.VirtualMachine = cov.OverrideVm


class CairoContractTest(TestCase):
    @classmethod
    async def setUp(cls):
        cls.starknet = await Starknet.empty()

        cls.contract = await cls.starknet.deploy(
            contract_class=get_contract_class(source=CONTRACT_FILE, disable_hint_validation=True),
            disable_hint_validation=True,
        )

    @mark.asyncio
    async def test_array_contract(self):
        res = await self.contract.view_product(array=PRODUCT_ARRAY).call()
        cov.report_runs()
