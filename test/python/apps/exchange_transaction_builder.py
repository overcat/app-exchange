from base64 import urlsafe_b64encode
from typing import Optional, Dict, Callable, Iterable
from enum import Enum, auto, IntEnum
from dataclasses import dataclass
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

from ragger.utils import prefix_with_len

from .pb.exchange_pb2 import NewFundResponse, NewSellResponse, NewTransactionResponse
from .signing_authority import SigningAuthority

from ..utils import int_to_minimally_sized_bytes, prefix_with_len_custom

class SignatureComputation(Enum):
    BINARY_ENCODED_PAYLOAD   = auto()
    # For SELL and FUND subcommand, prefix sign payload by a '.'
    DOT_PREFIXED_BASE_64_URL = auto()


class SignatureEncoding(Enum):
    DER       = auto()
    # For SELL subcommand, convert DER encoding to plain r,s
    PLAIN_R_S = auto()


class PayloadEncoding(Enum):
    BYTES_ARRAY = auto()
    BASE_64_URL = auto()


class SubCommand(IntEnum):
    SWAP = 0x00
    SELL = 0x01
    FUND = 0x02
    SWAP_NG = 0x03
    SELL_NG = 0x04
    FUND_NG = 0x05

SWAP_SUBCOMMANDS = [SubCommand.SWAP, SubCommand.SWAP_NG]
SELL_SUBCOMMANDS = [SubCommand.SELL, SubCommand.SELL_NG]
FUND_SUBCOMMANDS = [SubCommand.FUND, SubCommand.FUND_NG]
LEGACY_SUBCOMMANDS = [SubCommand.SWAP, SubCommand.SELL, SubCommand.FUND]
NEW_SUBCOMMANDS = [SubCommand.SWAP_NG, SubCommand.SELL_NG, SubCommand.FUND_NG]
ALL_SUBCOMMANDS = [SubCommand.SWAP, SubCommand.SELL, SubCommand.FUND, SubCommand.SWAP_NG, SubCommand.SELL_NG, SubCommand.FUND_NG]

@dataclass(frozen=True)
class SubCommandSpecs:
    partner_curve: ec.EllipticCurve
    signature_computation: SignatureComputation
    signature_encoding: SignatureEncoding
    default_payload_encoding: PayloadEncoding
    transaction_type: Callable
    required_fields: Iterable[str]
    transaction_id_field: str
    payout_field: str
    refund_field: Optional[str]

    def check_conf(self, conf: Dict) -> bool:
        return (all(i in conf for i in self.required_fields) and (len(conf) == len(self.required_fields)))

    def format_transaction(self, transaction: bytes, prefix_transaction: bool) -> bytes:
        if prefix_transaction == True:
            return b"." + transaction
        else:
            return transaction

    def encode_payload(self, raw_transaction: bytes, url_encode: bool) -> bytes:
        if url_encode == True:
            return urlsafe_b64encode(raw_transaction)
        else:
            return raw_transaction

    def encode_signature(self, signature_to_encode: bytes, r_s_encode: bool) -> bytes:
        if r_s_encode == True:
            r, s = decode_dss_signature(signature_to_encode)
            signature_to_encode = r.to_bytes(32, "big") + s.to_bytes(32, "big")
        return signature_to_encode

    def _create_transaction(self, conf: Dict, transaction_id: bytes) -> bytes:
        # Alter a copy of conf to not modify the actual conf
        c = conf.copy()
        c[self.transaction_id_field] = transaction_id
        raw_transaction = self.transaction_type(**c).SerializeToString()
        return self.encode_payload(raw_transaction, (self.default_payload_encoding == PayloadEncoding.BASE_64_URL))


SWAP_NG_SPECS: SubCommandSpecs = SubCommandSpecs(
    partner_curve = ec.SECP256R1(),
    signature_computation = SignatureComputation.DOT_PREFIXED_BASE_64_URL,
    signature_encoding = SignatureEncoding.PLAIN_R_S,
    default_payload_encoding = PayloadEncoding.BASE_64_URL,
    transaction_type = NewTransactionResponse,
    required_fields = ["payin_address", "payin_extra_id", "refund_address", "refund_extra_id",
                       "payout_address", "payout_extra_id", "currency_from", "currency_to",
                       "amount_to_provider", "amount_to_wallet"],
    transaction_id_field = "device_transaction_id_ng",
    payout_field = "currency_to",
    refund_field = "currency_from",
)

SWAP_SPECS: SubCommandSpecs = SubCommandSpecs(
    partner_curve = ec.SECP256K1(),
    signature_computation = SignatureComputation.BINARY_ENCODED_PAYLOAD,
    signature_encoding = SignatureEncoding.DER,
    default_payload_encoding = PayloadEncoding.BYTES_ARRAY,
    transaction_type = NewTransactionResponse,
    required_fields = ["payin_address", "payin_extra_id", "refund_address", "refund_extra_id",
                       "payout_address", "payout_extra_id", "currency_from", "currency_to",
                       "amount_to_provider", "amount_to_wallet"],
    transaction_id_field = "device_transaction_id",
    payout_field = "currency_to",
    refund_field = "currency_from",
)

SELL_NG_SPECS: SubCommandSpecs = SubCommandSpecs(
    partner_curve = ec.SECP256R1(),
    signature_computation = SignatureComputation.DOT_PREFIXED_BASE_64_URL,
    signature_encoding = SignatureEncoding.PLAIN_R_S,
    default_payload_encoding = PayloadEncoding.BASE_64_URL,
    transaction_type = NewSellResponse,
    transaction_id_field = "device_transaction_id",
    required_fields = ["trader_email", "in_currency", "in_amount", "in_address", "out_currency", "out_amount"],
    payout_field = "in_currency",
    refund_field = None,
)

# Legacy SELL specs happen to be the same as the unified specs
SELL_SPECS: SubCommandSpecs = SELL_NG_SPECS

FUND_NG_SPECS: SubCommandSpecs = SubCommandSpecs(
    partner_curve = ec.SECP256R1(),
    signature_computation = SignatureComputation.DOT_PREFIXED_BASE_64_URL,
    signature_encoding = SignatureEncoding.PLAIN_R_S,
    default_payload_encoding = PayloadEncoding.BASE_64_URL,
    transaction_type = NewFundResponse,
    required_fields = ["user_id", "account_name", "in_currency", "in_amount", "in_address"],
    transaction_id_field = "device_transaction_id",
    payout_field = "in_currency",
    refund_field =  None,
)

FUND_SPECS: SubCommandSpecs = SubCommandSpecs(
    partner_curve = ec.SECP256R1(),
    signature_computation = SignatureComputation.DOT_PREFIXED_BASE_64_URL,
    signature_encoding = SignatureEncoding.DER,
    default_payload_encoding = PayloadEncoding.BASE_64_URL,
    transaction_type = NewFundResponse,
    required_fields = ["user_id", "account_name", "in_currency", "in_amount", "in_address"],
    transaction_id_field = "device_transaction_id",
    payout_field = "in_currency",
    refund_field =  None,
)

SUBCOMMAND_TO_SPECS = {
    SubCommand.SWAP: SWAP_SPECS,
    SubCommand.SELL: SELL_SPECS,
    SubCommand.FUND: FUND_SPECS,
    SubCommand.SWAP_NG: SWAP_NG_SPECS,
    SubCommand.SELL_NG: SELL_NG_SPECS,
    SubCommand.FUND_NG: FUND_NG_SPECS,
}

def craft_pb(subcommand: SubCommand, tx_infos: Dict, transaction_id: bytes) -> bytes:
    subcommand_specs = SUBCOMMAND_TO_SPECS[subcommand]
    assert subcommand_specs.check_conf(tx_infos)
    return subcommand_specs._create_transaction(tx_infos, transaction_id)

def encode_transaction_signature(subcommand: SubCommand, signer: SigningAuthority, tx: bytes) -> bytes:
    subcommand_specs = SUBCOMMAND_TO_SPECS[subcommand]
    prefix_transaction = True if (subcommand_specs.signature_computation == SignatureComputation.DOT_PREFIXED_BASE_64_URL) else False
    formated_transaction = subcommand_specs.format_transaction(tx, prefix_transaction)
    signed_transaction = signer.sign(formated_transaction)
    r_s_encode = True if (subcommand_specs.signature_encoding == SignatureEncoding.PLAIN_R_S) else False
    encoded_signature = subcommand_specs.encode_signature(signed_transaction, r_s_encode)

    if subcommand == SubCommand.SWAP_NG or subcommand == SubCommand.SELL_NG or subcommand == SubCommand.FUND_NG:
        dot_prefix = int.to_bytes(1 if prefix_transaction == True else False, 1, byteorder='big')
        rs_encode = int.to_bytes(1 if r_s_encode == True else False, 1, byteorder='big')
        encoded_signature = dot_prefix + rs_encode + encoded_signature
    return encoded_signature

def craft_transaction(subcommand: SubCommand, transaction: bytes, fees: int) -> bytes:
    subcommand_specs = SUBCOMMAND_TO_SPECS[subcommand]
    fees_bytes = int_to_minimally_sized_bytes(fees)
    prefix_length = 2 if (subcommand == SubCommand.SWAP_NG or subcommand == SubCommand.FUND_NG or subcommand == SubCommand.SELL_NG) else 1
    payload = prefix_with_len_custom(transaction, prefix_length) + prefix_with_len(fees_bytes)
    if subcommand == SubCommand.SWAP_NG or subcommand == SubCommand.FUND_NG or subcommand == SubCommand.SELL_NG:
        payload = int.to_bytes(1, 1, byteorder='big') + payload
    return payload

def craft_and_sign_tx(subcommand: SubCommand, tx_infos: Dict, transaction_id: bytes, fees: int, signer: SigningAuthority):
    pb = craft_pb(subcommand, tx_infos, transaction_id)
    tx = craft_transaction(subcommand, pb, fees)
    signed_tx = encode_transaction_signature(subcommand, signer, pb)
    return tx, signed_tx

def extract_payout_ticker(subcommand: SubCommand, tx_infos: Dict) -> str:
    subcommand_specs = SUBCOMMAND_TO_SPECS[subcommand]
    return tx_infos[subcommand_specs.payout_field]

def extract_refund_ticker(subcommand: SubCommand, tx_infos: Dict) -> Optional[str]:
    subcommand_specs = SUBCOMMAND_TO_SPECS[subcommand]
    if subcommand_specs.refund_field:
        return tx_infos[subcommand_specs.refund_field]
    else:
        return None

def get_partner_curve(subcommand: SubCommand) -> ec.EllipticCurve:
    return SUBCOMMAND_TO_SPECS[subcommand].partner_curve

def get_credentials(subcommand: SubCommand, partner: SigningAuthority) -> bytes:
    if subcommand == SubCommand.SWAP_NG or subcommand == SubCommand.SELL_NG or subcommand == SubCommand.FUND_NG:
        return partner.credentials_ng
    else:
        return partner.credentials
