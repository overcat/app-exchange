import pytest

from .apps.exchange_test_runner import ExchangeTestRunner, ALL_TESTS_EXCEPT_MEMO
from .apps.tezos import TezosClient, encode_address, XTZ_PACKED_DERIVATION_PATH, StatusCode

from requests.exceptions import ChunkedEncodingError, ConnectionError
from urllib3.exceptions import ProtocolError
from http.client import IncompleteRead

# A bit hacky but way less hassle than actually writing an actual address decoder
TEZOS_ADDRESS_DECODER = {
    encode_address("e6330795ffe18f873b83cb13662442b87bd98c22"): "e6330795ffe18f873b83cb13662442b87bd98c22",
    encode_address("e6330795ffe18f873b83cb13662442b87bd98c40"): "e6330795ffe18f873b83cb13662442b87bd98c40",
}

# ExchangeTestRunner implementation for Stellar
class TezosTests(ExchangeTestRunner):
    currency_ticker = "XTZ"
    valid_destination_1 = encode_address("e6330795ffe18f873b83cb13662442b87bd98c22")
    valid_destination_memo_1 = ""
    valid_destination_2 = encode_address("e6330795ffe18f873b83cb13662442b87bd98c40")
    valid_destination_memo_2 = "0"
    valid_refund = "tz1YPjCVqgimTAPmxZX9egDeTFRCmrTRqmp9"
    valid_refund_memo = ""
    valid_send_amount_1 = 10000000
    valid_send_amount_2 = 446739662
    valid_fees_1 = 100
    valid_fees_2 = 10078
    fake_refund = "abcdabcd"
    fake_refund_memo = ""
    fake_payout = "abcdabcd"
    fake_payout_memo = ""
    signature_refusal_error_code = StatusCode.EXC_REJECT

    def perform_final_tx(self, destination, send_amount, fees, memo):
        decoded_destination = TEZOS_ADDRESS_DECODER[destination]
        TezosClient(self.backend).send_simple_sign_tx(path=XTZ_PACKED_DERIVATION_PATH,
                                                      fees=fees,
                                                      memo=memo,
                                                      destination=decoded_destination,
                                                      send_amount=send_amount)

        # TODO : assert signature validity


# Use a class to reuse the same Speculos instance
# class TestsTezos:
# TODO: Restore the class after the return in exchange in Tezos is merged

@pytest.mark.parametrize('test_to_run', ALL_TESTS_EXCEPT_MEMO)
def test_tezos(backend, exchange_navigation_helper, test_to_run):
    if "double_sign" in test_to_run:
        # The double_sign protection in Tezos quits after the first send which breaks the generic TestRunner
        # TODO: Remove this special handling after the return in exchange in Tezos is merged
        with pytest.raises((ChunkedEncodingError, ConnectionError, ProtocolError, IncompleteRead)):
            TezosTests(backend, exchange_navigation_helper).run_test(test_to_run)
    else:
        TezosTests(backend, exchange_navigation_helper).run_test(test_to_run)
