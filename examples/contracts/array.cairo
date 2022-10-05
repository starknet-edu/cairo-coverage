%lang starknet

from starkware.cairo.common.cairo_builtins import HashBuiltin
from starkware.starknet.common.syscalls import get_contract_address
from starkware.cairo.common.registers import get_fp_and_pc
from examples.contracts.lib import BasicStruct, array_product

@view
func view_product{syscall_ptr: felt*, pedersen_ptr: HashBuiltin*, range_check_ptr}(
    array_len: felt, array: BasicStruct*
) -> (res: felt) {
    alloc_locals;
    let (__fp__, _) = get_fp_and_pc();
    let (res) = array_product(array_len, array);
    let (add) = get_contract_address();
    return (res + add,);
}
@view
func view_produc1t{syscall_ptr: felt*, pedersen_ptr: HashBuiltin*, range_check_ptr}(
    array_len: felt, array: BasicStruct*
) -> (res: felt) {
    alloc_locals;
    let (__fp__, _) = get_fp_and_pc();
    let (res) = array_product(array_len, array);
    let (add) = get_contract_address();
    return (res + add,);
}
@view
func view_produc2t{syscall_ptr: felt*, pedersen_ptr: HashBuiltin*, range_check_ptr}(
    array_len: felt, array: BasicStruct*
) -> (res: felt) {
    alloc_locals;
    let (__fp__, _) = get_fp_and_pc();
    let (res) = array_product(array_len, array);
    let (add) = get_contract_address();
    return (res + add,);
}
@view
func view_produc3t{syscall_ptr: felt*, pedersen_ptr: HashBuiltin*, range_check_ptr}(
    array_len: felt, array: BasicStruct*
) -> (res: felt) {
    alloc_locals;
    let (__fp__, _) = get_fp_and_pc();
    let (res) = array_product(array_len, array);
    let (add) = get_contract_address();
    return (res + add,);
}
@view
func view_produc4t{syscall_ptr: felt*, pedersen_ptr: HashBuiltin*, range_check_ptr}(
    array_len: felt, array: BasicStruct*
) -> (res: felt) {
    alloc_locals;
    let (__fp__, _) = get_fp_and_pc();
    let (res) = array_product(array_len, array);
    let (add) = get_contract_address();
    return (res + add,);
}
