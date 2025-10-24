"""An opinionated job to update device names."""

import logging
import re

from django.db.models import Model
from nautobot.apps.jobs import register_jobs
from nautobot.dcim.models import Device, DeviceType, FrontPort, Location, RearPort

from .base import BaseJob, BaseJobButton, DeviceSelectJobMixin, UpdateMixin
from .util import filter_kwargs


class UpdatePortLabelsMixin(UpdateMixin[Device]):
    """Mixin class containing the port labeling logic."""

    logger: logging.Logger
    update_type = Device

    def update_object(self, object: Device) -> None:
        """Update the front and rear ports for the given device."""
        for ports in [object.front_ports, object.rear_ports]:
            port: FrontPort | RearPort
            for port in ports.all():
                port_name = f"{object.name}:{port.name}"
                match = re.search(r"(\d+)$", port.name)
                if not match:
                    self.logger.warning(f"{port._meta.verbose_name} '{port_name}' does not end with digits. Skipping.")
                    continue

                port_index = match.group(1)
                new_label = f"{object.name}-{port_index}"

                if port.label != new_label:
                    self.logger.info(f"Updating port '{port_name}' to '{new_label}'")
                    port.label = new_label
                    port.validated_save()


class UpdatePortLabelsButton(BaseJobButton, UpdatePortLabelsMixin):
    """Update Port Labels.

    This is a job button receiver that will call the Update Device Port Labels
    job when clicked from a device, location, or device type detail page.
    """

    class Meta:  # noqa:D106
        has_sensitive_variables = False

    def receive_job_button(self, obj: Model):
        """Run the job when the button has been pushed."""
        super().receive_job_button(obj)
        kwargs = filter_kwargs(obj, objects=Device, location=Location, device_type=DeviceType)
        self.update_objects(**kwargs)


class UpdatePortLabels(DeviceSelectJobMixin, BaseJob, UpdatePortLabelsMixin):
    """Update Port Labels.

    This job will iterate through all front and rear ports for selected devices and
    will update their labels according to the specified naming convention. It
    ensures that port labels are consistent and follow organizational standards.

    The naming convention is as follows:
    [Device Name]-[digit]

    If an existing port label does not include trailing digits, it will be skipped.
    Additionally, there could be duplicate labels for different port types that have
    the same trailing digit. For instance, "Coax 1" and "Ethernet 1" for the device
    "BR-AP1". These would both resolve to "BR-AP1-1". The assumption is that the connector
    type is used to determine which of the duplicate labeled ports is the correct port.
    """

    class Meta:  # noqa:D106
        has_sensitive_variables = False


name = "Device Utilities"
register_jobs(UpdatePortLabels, UpdatePortLabelsButton)
