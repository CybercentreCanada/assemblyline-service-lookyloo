"""This Assemblyline service extracts artifacts and captures from potentially malicious URLs using Lookyloo."""

from assemblyline.common import forge
from assemblyline_v4_service.common.base import ServiceBase
from assemblyline_v4_service.common.request import ServiceRequest
from assemblyline_v4_service.common.result import Result


class Lookyloo(ServiceBase):
    """This Assemblyline service extracts artifacts and captures from potentially malicious URLs using Lookyloo."""

    def execute(self, request: ServiceRequest):
        """Run the service."""

        result = Result()
        request.result = result
