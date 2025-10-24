"""Unit tests for the device component update job."""

import logging
import re
from unittest.mock import Mock

from django.db.models import Q
from nautobot.apps.testing import TestCase
from nautobot.dcim.models import (
    Device,
    DeviceType,
    Location,
)

from ..device_names import UpdateDeviceNames, UpdateDeviceNamesButton
from .fixtures import add_device, add_device_type, add_location, add_location_type, add_role


class DeviceNamesTestCase(TestCase):
    """Base test case with fixtures."""

    def setUp(self):
        """Set up test data."""
        super().setUp()
        role = add_role("SW", Device)
        location_type = add_location_type("Site", [Device])
        location1 = add_location("S1", location_type)
        location2 = add_location("S2", location_type)

        device_type1 = add_device_type("Manufacturer", "Model 1")
        device_type2 = add_device_type("Manufacturer", "Model 2")

        add_device("device 1", device_type1, location1, role)
        add_device("device 2", device_type2, location1, role)
        add_device("device 3", device_type1, location2, role)
        add_device("device 4", device_type2, location2, role)
        add_device("device abc", device_type2, location2, role)


class TestUpdateDeviceNamesJob(DeviceNamesTestCase):
    """Unit tests for the UpdateDevicesNames job."""

    def setUp(self):
        """Set up test data."""
        super().setUp()
        self.job = UpdateDeviceNames()

    def test_update_by_location(self):
        """Test that all devices are updated for a location."""
        location = Location.objects.get(name="S1")
        self.job.run(log_level=logging.INFO, location=location, device_type=None, devices=None)

        for device in Device.objects.filter(location=location):
            self.assertRegex(device.name, f"^{location.name}-SW\\d+$")

        # make sure devices in other locations were not updated
        for device in Device.objects.exclude(location=location):
            self.assertFalse(re.match(f"^{location.name}-SW\\d+$", device.name))

    def test_update_by_device_type(self):
        """Test that all devices are updated for a device_type."""
        device_type = DeviceType.objects.get(model="Model 1")
        self.job.run(log_level=logging.INFO, location=None, device_type=device_type, devices=None)

        for device in Device.objects.filter(device_type=device_type):
            location = device.location
            self.assertRegex(device.name, f"^{location.name}-SW\\d+$")

        # make sure devices of other device types were not updated
        for device in Device.objects.exclude(device_type=device_type):
            location = device.location
            self.assertFalse(re.match(f"^{location.name}-SW\\d+$", device.name))

    def test_update_by_devices(self):
        """Test that all provided devices are updated."""
        devices = Device.objects.filter(name__in=["device 1", "device 4"])
        query = Q(id=devices[0].id) | Q(id=devices[1].id)

        self.job.run(log_level=logging.INFO, location=None, device_type=None, devices=devices)

        for device in Device.objects.filter(query):
            location = device.location
            self.assertRegex(device.name, f"^{location.name}-SW\\d+$")

        # make sure other devices were not updated
        for device in Device.objects.exclude(query):
            location = device.location
            self.assertFalse(re.match(f"^{location.name}-SW\\d+$", device.name))

    def test_log_unmatched_devices(self):
        """Test that devices without trailing digits are logged and skipped."""
        with self.assertLogs(self.job.logger, level="INFO") as log:
            devices = Device.objects.all()
            self.job.run(log_level=logging.INFO, location=None, device_type=None, devices=devices)
            self.assertIn(
                "WARNING:workspace.jobs.device_names:Device 'device abc' does not end with digits. Skipping.",
                log.output,
            )


class TestUpdateDeviceNamesButton(DeviceNamesTestCase):
    """Unit tests for the UpdateDeviceNames job button receiver."""

    def setUp(self):
        """Set up test data."""
        super().setUp()
        self.button = UpdateDeviceNamesButton()
        self.button.update_objects = Mock()

    def test_device_provided(self):
        """Confirm that providing a device calls the job with that device."""
        device = Device.objects.get(name="device 1")
        self.button.receive_job_button(device)
        self.button.update_objects.assert_called_once_with(
            objects=device,
            location=None,
            device_type=None,
        )

    def test_device_type_provided(self):
        """Confirm that providing a device calls the job with that device."""
        device_type = DeviceType.objects.get(model="Model 1")
        self.button.receive_job_button(device_type)
        self.button.update_objects.assert_called_once_with(
            objects=None,
            location=None,
            device_type=device_type,
        )

    def test_location_type_provided(self):
        """Confirm that providing a device calls the job with that device."""
        location = Location.objects.get(name="S1")
        self.button.receive_job_button(location)
        self.button.update_objects.assert_called_once_with(
            objects=None,
            location=location,
            device_type=None,
        )
