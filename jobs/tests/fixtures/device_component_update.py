"""Fixtures needed for the device_component_update tests."""

from nautobot.dcim.models import Device

from .util import (
    add_device,
    add_device_type,
    add_front_port_template,
    add_interface_template,
    add_location,
    add_location_type,
    add_role,
)


def add_fixtures():
    """Add fixtures for device_component_update tests."""
    role = add_role("Device", Device)
    location_type = add_location_type("Site", [Device])
    location = add_location("Site", location_type)
    device_type = add_device_type("Manufacturer", "Model")
    add_interface_template("Interface", device_type, label="Ethernet1")
    add_front_port_template("Front Port", "Rear Port", device_type)

    add_device("device", device_type, location, role)
