%lang starknet

from starkware.cairo.common.cairo_builtins import HashBuiltin
struct BasicStruct {
    first_member: felt,
    second_member: felt,
}

func array_product{syscall_ptr: felt*, pedersen_ptr: HashBuiltin*, range_check_ptr}(
    array_len: felt, array: BasicStruct*
) -> (res: felt) {
    if (array_len == 0) {
        return (0,);
    } else {
        let temp = [array].first_member * [array].second_member;
        let (temp2) = array_product(array_len - 1, array);
        let res = temp * temp2;
        return (res,);
    }
}
