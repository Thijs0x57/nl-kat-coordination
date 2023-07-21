import json
from typing import Dict, Iterable, Union

from boefjes.job_models import NormalizerMeta
from octopoes.models import OOI, Reference
from octopoes.models.ooi.service import SSLCipher


def parse_cipher(cipher: str) -> Union[Dict, None]:
    parts = cipher.split()
    if len(parts) == 8:
        cipher_dict = {
            "protocol": parts[0],
            "cipher_suite_code": parts[1],
            "cipher_suite_name": parts[2],
            "key_exchange_algorithm": parts[3],
            "bits": parts[4],
            "encryption_algorithm": parts[5],
            "key_size": parts[6],
            "cipher_suite_alias": parts[7],
        }
        return cipher_dict


def run(normalizer_meta: NormalizerMeta, raw: Union[bytes, str]) -> Iterable[OOI]:
    boefje_meta = normalizer_meta.raw_data.boefje_meta
    input_ooi = Reference.from_str(boefje_meta.input_ooi)
    output = json.loads(raw)

    for item in output:
        cipher = parse_cipher(item["finding"])
        if cipher:
            yield SSLCipher(
                ip_service=input_ooi,
                protocol=cipher["protocol"],
                suite=cipher["cipher_suite_name"],
                bits=int(cipher["bits"]),
                key_size=int(cipher["key_size"]),
            )
