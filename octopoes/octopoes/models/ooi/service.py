from typing import Literal, Optional

from octopoes.models import OOI, Reference
from octopoes.models.ooi.network import IPPort
from octopoes.models.persistence import ReferenceField


class Service(OOI):
    object_type: Literal["Service"] = "Service"

    name: str

    _natural_key_attrs = ["name"]
    _information_value = ["name"]
    _traversable = False

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        return reference.tokenized.name


class IPService(OOI):
    object_type: Literal["IPService"] = "IPService"

    ip_port: Reference = ReferenceField(IPPort, max_issue_scan_level=0, max_inherit_scan_level=4)
    service: Reference = ReferenceField(Service, max_issue_scan_level=1, max_inherit_scan_level=0)

    _natural_key_attrs = ["ip_port", "service"]

    _reverse_relation_names = {"ip_port": "services", "service": "services"}

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        t = reference.tokenized
        ip_address = t.ip_port.address.address
        return f"{t.service.name}://{ip_address}:{t.ip_port.port}/{t.ip_port.protocol}"


class SSLCipher(OOI):
    object_type: Literal["SSLCipher"] = "SSLCipher"

    ip_service: Reference = ReferenceField(IPService, max_issue_scan_level=0, max_inherit_scan_level=4)
    protocol: str
    suite: str

    bits: int
    key_size: Optional[int]

    _natural_key_attrs = ["ip_service", "protocol", "suite"]

    _reverse_relation_names = {"ip_service": "ciphers"}

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        t = reference.tokenized
        ip_address = t.ip_service.ip_port.address.address
        return f"{t.protocol} {t.suite} {str(ip_address)}:{t.ip_service.ip_port.port}"
