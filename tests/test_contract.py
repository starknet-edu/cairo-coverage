import os
from contextlib import contextmanager
from dataclasses import dataclass

import pytest
from asynctest import TestCase
from starkware.crypto.signature.signature import private_to_stark_key
from starkware.starknet.testing.starknet import Starknet
from starkware.starkware_utils.error_handling import StarkException

from tests import cov


@dataclass
class Uint256:
    """Uint256 dataclass to ease the asserting process"""

    low: int  # 2**128 low bits
    high: int  # 2**128 high bits

    def __eq__(self, __o: object) -> bool:
        """__eq__ method allows to do a == b (a and b being Uints256)"""
        return self.low == __o.low and self.high == __o.high


@dataclass
class SignedProposal:
    """SignedProposal (event) dataclass to ease the asserting process"""

    signer: int
    proposal_nb: Uint256
    signer_nb: Uint256

    def __eq__(self, __o: object) -> bool:
        """__eq__ method allows to do a == b (a and b being SignedProposal events)"""

        return self.signer == __o.signer and self.proposal_nb == __o.proposal_nb and self.signer_nb == __o.signer_nb


@dataclass
class ExecutedProposal:
    """ExecutedProposal (event) dataclass to ease the asserting process"""

    signer: int
    amount: Uint256
    to_: int
    token: int

    def __eq__(self, __o: object) -> bool:
        """__eq__ method allows to do a == b (a and b being ExecutedProposal events)"""
        return (
            self.signer == __o.signer and self.amount == __o.amount and self.to_ == __o.to_ and self.token == __o.token
        )


@dataclass
class Proposal:
    """Proposal dataclass to ease the asserting process"""

    amount: Uint256
    to_: int
    executed: int
    numberOfSigners: Uint256
    targetERC20: int
    timestamp: int

    def __eq__(self, __o: object) -> bool:
        """__eq__ method allows to do a == b (a and b being Proposals)"""

        return (
            self.amount == __o.amount
            and self.to_ == __o.to_
            and self.executed == __o.executed
            and self.numberOfSigners == __o.numberOfSigners
            and self.targetERC20 == __o.targetERC20
            and self.timestamp == __o.timestamp
        )


# The path to the contract source code.
CONTRACT_FILE = os.path.join("contracts", "contract_final.cairo")
# The path to the mockERC20 source code.
MOCKERC20_FILE = os.path.join("contracts", "ERC20.cairo")


# Defining the various signers addresses
signer1 = private_to_stark_key(123)
signer2 = private_to_stark_key(1234)
signer3 = private_to_stark_key(12345)
signer4 = private_to_stark_key(123456)
signer5 = private_to_stark_key(1234567)

# allowed signers
signers = [signer1, signer2, signer3, signer4]

# calldata for the constructor of the multisig contract
multisig_calldata = [4, *signers, 3, 0]


class CairoContractTest(TestCase):
    """Test class inherits from TestCase. to inherit all the asserts and for it to be detected as a unit test file)"""

    @classmethod
    async def setUp(cls):
        """This method is called before each test method"""
        cls.starknet = await Starknet.empty()  # create a mock starknet instance
        cls.multisig = await cls.starknet.deploy(  # deploy the multisig contract
            source=CONTRACT_FILE, constructor_calldata=multisig_calldata
        )
        mockERC20_calldata = [  # mockERC20 constructor calldata
            1,
            1,
            0,
            100,
            0,
            cls.multisig.contract_address,
        ]
        cls.mockERC20 = await cls.starknet.deploy(  # deploy the mockERC20
            source=MOCKERC20_FILE,
            constructor_calldata=mockERC20_calldata,
        )
        cls.maxDiff = None  # we want strict equality between felts so no max diff

        await cls.multisig.create_proposal(  # a signer creates a proposal
            amount=(1, 0), to_=signer1, targetERC20=cls.mockERC20.contract_address
        ).execute(
            caller_address=signer1
        )  # signer 1 creates the proposal

    @contextmanager
    def raisesCairoError(self, error_message):
        """Context manager to assert for starknet errors"""
        with self.assertRaises(StarkException) as error_msg:
            yield error_msg
        self.assertTrue(f"Error message: {error_message}" in str(error_msg.exception.message))

    @pytest.mark.asyncio
    async def test_create_proposal(self):
        """Test everything about creating a proposal"""
        expected_proposal = Proposal(
            amount=Uint256(low=1, high=0),
            to_=signer1,
            executed=int(False),
            numberOfSigners=Uint256(low=1, high=0),
            targetERC20=self.mockERC20.contract_address,
            timestamp=0,
        )

        execution_info = await self.multisig.view_proposal(proposal_nb=(0, 0)).call()

        # assert that the actual proposal is the one we expected
        self.assertEqual(execution_info.result.proposal, expected_proposal)

        signer = await self.multisig.view_approved_signer(proposal_nb=(0, 0), signer_nb=(0, 0)).call()
        # assert that the creator of the proposal is added in the approved signers
        self.assertEqual(signer.result.signer, signer1)

        # assert that only whitelisted addresses can create a proposal
        with self.raisesCairoError("Only signer"):
            await self.multisig.create_proposal(
                amount=(1, 0), to_=signer1, targetERC20=self.mockERC20.contract_address
            ).execute(caller_address=signer5)

    @pytest.mark.asyncio
    async def test_sign_proposal(self):
        """Test everything about signing a proposal"""
        expected_result = Proposal(
            amount=Uint256(low=1, high=0),
            to_=signer1,
            executed=int(False),
            numberOfSigners=Uint256(low=2, high=0),
            targetERC20=self.mockERC20.contract_address,
            timestamp=0,
        )
        expected_event = SignedProposal(signer2, Uint256(0, 0), signer_nb=Uint256(2, 0))

        # signer signs proposal should work
        res = await self.multisig.sign_proposal(proposal_nb=(0, 0)).execute(caller_address=signer2)
        execution_info = await self.multisig.view_proposal(proposal_nb=(0, 0)).call()
        # check that signing the proposal emitted the right event
        self.assertEqual(res.main_call_events.pop(), expected_event)
        # check that the proposal has been updated
        self.assertEqual(execution_info.result.proposal, expected_result)

        signer = await self.multisig.view_approved_signer(proposal_nb=(0, 0), signer_nb=(1, 0)).call()
        # check that the approved signers have been updated
        self.assertEqual(signer.result.signer, signer2)

        # signer has already signed should not work
        with self.raisesCairoError("Sender has already signed"):
            await self.multisig.sign_proposal(proposal_nb=(0, 0)).execute(caller_address=signer2)

        # unknown tries to sign should not work
        with self.raisesCairoError("Only signer"):
            await self.multisig.sign_proposal(proposal_nb=(0, 0)).execute(caller_address=signer5)

        # unknown tries to sign unknown proposal, should not work
        with self.raisesCairoError("Only signer"):
            await self.multisig.sign_proposal(proposal_nb=(1, 0)).execute(caller_address=signer5)

        # signer tries to sign unknown proposal should not work
        with self.raisesCairoError("Proposal doesn't exist"):
            await self.multisig.sign_proposal(proposal_nb=(1, 0)).execute(caller_address=signer1)

        # signer signs proposal and executes it
        expected_result = Proposal(
            amount=Uint256(low=1, high=0),
            to_=signer1,
            executed=int(True),
            numberOfSigners=Uint256(low=3, high=0),
            targetERC20=self.mockERC20.contract_address,
            timestamp=0,
        )
        expected_end_balance = Uint256(low=1, high=0)
        expected_signer_event = SignedProposal(signer3, Uint256(0, 0), signer_nb=Uint256(3, 0))
        expected_execute_event = ExecutedProposal(signer3, Uint256(1, 0), signer1, self.mockERC20.contract_address)

        res = await self.multisig.sign_proposal(proposal_nb=(0, 0)).execute(caller_address=signer3)
        execution_info = await self.multisig.view_proposal(proposal_nb=(0, 0)).call()
        end_balance = await self.mockERC20.balanceOf(account=signer1).call()
        signer = await self.multisig.view_approved_signer(proposal_nb=(0, 0), signer_nb=(2, 0)).call()
        cov.report_runs(out_file="report.json")

        # check that the first event to be emitted is the execution event
        self.assertEqual(res.main_call_events[0], expected_execute_event)
        # check that the second event to be emitted is the signing event
        self.assertEqual(res.main_call_events[1], expected_signer_event)
        # check that the proposal have been updated
        self.assertEqual(execution_info.result.proposal, expected_result)
        # check that the approved signer have been updated
        self.assertEqual(signer.result.signer, signer3)
        # check that the proposal has been executed by check the signer 1's balance
        self.assertEqual(end_balance.result.balance, expected_end_balance)
