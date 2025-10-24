"""An opinionated job to update device names."""

import logging
import re

from nautobot.apps.jobs import register_jobs
from nautobot.dcim.models import Device, DeviceType, Location

from .base import BaseJob, BaseJobButton, DeviceSelectJobMixin, UpdateMixin
from .util import filter_kwargs


class UpdateDeviceNamesMixin(UpdateMixin[Device]):
    """Mixin class containing the device name update logic."""

    logger: logging.Logger
    update_type = Device

    def update_object(self, object: Device) -> None:
        """Update the device name based on the naming convention."""
        print(f"Updating {object.name}")
        match = re.search(r"(\d+)$", object.name)
        if not match:
            self.logger.warning(f"Device '{object.name}' does not end with digits. Skipping.")
            return

        device_index = match.group(1)
        new_name = f"{object.location.name}-{object.role.name}{device_index}"

        if object.name != new_name:
            self.logger.info(f"Updating device '{object.name}' to '{new_name}'")
            object.name = new_name
            object.save()


class UpdateDeviceNamesButton(BaseJobButton, UpdateDeviceNamesMixin):
    """Update Device Names.

    This is a job button receiver that will call the Update Device Names job
    when clicked from a device, location or device type detail page.
    """

    class Meta:  # noqa:D106
        has_sensitive_variables = False

    def receive_job_button(self, obj: Device | DeviceType | Location):
        """Run the job when the button has been pushed."""
        super().receive_job_button(obj)
        kwargs = filter_kwargs(obj, objects=Device, location=Location, device_type=DeviceType)
        self.update_objects(**kwargs)


class UpdateDeviceNames(DeviceSelectJobMixin, BaseJob, UpdateDeviceNamesMixin):
    """Update Device Names.

    This job will iterate through all devices in the system and update their names
    according to the specified naming convention. It ensures that device names are
    consistent and follow organizational standards.

    The naming convention is as follows:
    [Location Name]-[Device Role][digits]

    If an existing device name does not include trailing digits, it will be skipped.
    """

    class Meta:  # noqa:D106
        has_sensitive_variables = False


name = "Device Utilities"
register_jobs(UpdateDeviceNames, UpdateDeviceNamesButton)
