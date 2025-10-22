"""An opinionated job to update device names."""

import logging
import re

from django.db.models import Model, Q, QuerySet
from nautobot.apps.jobs import MultiObjectVar, ObjectVar, register_jobs
from nautobot.dcim.models import Device, DeviceType, Location

from .base import BaseJob, BaseJobButton


class UpdateDeviceNamesMixin:
    """Mixin class containing the device name update logic."""

    logger: logging.Logger

    def update_device_name(self, device: Device) -> None:
        """Update the device name based on the naming convention."""
        match = re.search(r"(\d+)$", device.name)
        if not match:
            self.logger.warning(f"Device '{device.name}' does not end with a digit. Skipping.")
            return

        device_index = match.group(1)
        new_name = f"{device.location.name}-{device.role.name}{device_index}"

        if device.name != new_name:
            self.logger.info(f"Updating device '{device.name}' to '{new_name}'")
            device.name = new_name
            device.save()

    def update(
        self,
        location: Location | None,
        device_type: DeviceType | None,
        devices: list[Device] | QuerySet[Device] | None,
    ) -> None:
        """Execute the job to update device names."""
        self.logger.info("Starting device name update process...")

        if devices is None or len(devices) == 0:
            filter = Q()
            for field_name, constraint in [("location", location), ("device_type", device_type)]:
                if constraint:
                    filter &= Q(**{field_name: constraint})
            devices = Device.objects.filter(filter)

        for device in devices:
            self.update_device_name(device)
        self.logger.info("Device name update process completed.")


class UpdateDeviceNamesButton(BaseJobButton, UpdateDeviceNamesMixin):
    """Update Device Names.

    This is a job button receiver that will call the Update Device Names job
    when clicked from a device, location or device type detail page.
    """

    class Meta:  # noqa:D106
        has_sensitive_variables = False

    def receive_job_button(self, obj: Model):
        """Run the job when the button has been pushed."""
        super().receive_job_button(obj)
        kwargs = {}
        if isinstance(obj, Device):
            kwargs["devices"] = [obj]
        elif isinstance(obj, Location):
            kwargs["location"] = obj
        elif isinstance(obj, DeviceType):
            kwargs["device_type"] = obj
        self.update(**kwargs)


class UpdateDeviceNames(BaseJob, UpdateDeviceNamesMixin):
    """Update Device Names.

    This job will iterate through all devices in the system and update their names
    according to the specified naming convention. It ensures that device names are
    consistent and follow organizational standards.

    The naming convention is as follows:
    [Location Name]-[Device Role][digit]
    """

    location = ObjectVar(label="Location", model=Location, required=False)

    device_type = ObjectVar(label="Device Type", model=DeviceType, required=False)

    devices = MultiObjectVar(
        label="Devices",
        model=Device,
        query_params={"device_type_id": "$device_type", "location_id": "$location"},
        required=False,
    )

    def run(
        self,
        log_level: str,
        location: Location | None,
        device_type: DeviceType | None,
        devices: QuerySet[Device] | None,
    ) -> None:
        """Execute the job to update device names."""
        super().run(log_level)

        self.update(location, device_type, devices)


name = "Device Utilities"
register_jobs(UpdateDeviceNames, UpdateDeviceNamesButton)
