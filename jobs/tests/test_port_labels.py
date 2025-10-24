"""Unit tests for the device component update job."""

import logging
from unittest.mock import Mock

from django.db.models import Q
from nautobot.apps.testing import TestCase
from nautobot.dcim.models import (
    Device,
)

from ..port_labels import UpdatePortLabels, UpdatePortLabelsButton
from .fixtures import (
    add_device,
    add_device_type,
    add_front_port_template,
    add_location,
    add_location_type,
    add_role,
)


class PortLabelsTestCase(TestCase):
    """Base test case with fixtures."""

    def setUp(self):
        """Set up test data."""
        super().setUp()
        role = add_role("SW", Device)
        location_type = add_location_type("Site", [Device])
        location = add_location("S1", location_type)
        device_type = add_device_type("Manufacturer", "Model")

        add_front_port_template("Front Port 1", "Rear Port 1", device_type)
        add_front_port_template("Front Port 2", "Rear Port 2", device_type)
        add_front_port_template("Front Port A", "Rear Port A", device_type)

        self.device = add_device("S1-SW", device_type, location, role)


class TestUpdatePortLabelsJob(PortLabelsTestCase):
    """Unit tests for the UpdateDevicesNames job."""

    def setUp(self):
        """Set up test data."""
        super().setUp()
        self.job = UpdatePortLabels()

    def test_update_by_devices(self):
        """Test that all provided devices are updated."""
        with self.assertLogs(self.job.logger, level="INFO") as log:
            self.job.run(
                log_level=logging.INFO,
                location=None,
                device_type=None,
                devices=Device.objects.filter(pk=self.device.pk),
            )
            self.assertIn(
                "WARNING:workspace.jobs.port_labels:front port 'S1-SW:Front Port A' does not end with digits. Skipping.",
                log.output,
            )

            self.assertIn(
                "WARNING:workspace.jobs.port_labels:rear port 'S1-SW:Rear Port A' does not end with digits. Skipping.",
                log.output,
            )
        self.device.refresh_from_db()

        query = Q(label__startswith="S1-SW-")
        for ports in [
            self.device.front_ports.filter(query).order_by("label"),
            self.device.rear_ports.filter(query).order_by("label"),
        ]:
            self.assertEquals(2, len(ports))
            for i in range(1, 3):
                self.assertEqual(f"S1-SW-{i}", ports[i - 1].label)


class TestUpdateDeviceNamesButton(PortLabelsTestCase):
    """Unit tests for the UpdateDeviceNames job button receiver."""

    def setUp(self):
        """Set up test data."""
        super().setUp()
        self.button = UpdatePortLabelsButton()
        self.button.update_objects = Mock()

    def test_device_provided(self):
        """Confirm that providing a device calls the job with that device."""
        self.button.receive_job_button(self.device)
        self.button.update_objects.assert_called_once_with(
            objects=self.device,
            location=None,
            device_type=None,
        )
