"""Fixtures module for creating data models for testing."""

from django.contrib.contenttypes.models import ContentType
from django.db.models import Model
from nautobot.dcim.models import Device, DeviceType, InterfaceTemplate, Location, LocationType, Manufacturer
from nautobot.extras.models import Role, Status


def add_role(name: str, *model_types: type[Model]) -> Role:
    """Add a role with the given name and associated content types."""
    role, created = Role.objects.get_or_create(name=name)
    if created:
        content_types = ContentType.objects.get_for_models(*model_types)
        role.content_types.set(content_types.values())
    return role


def add_location_type(name: str, model_types: list[type[Model]], *ancestry) -> LocationType:
    """Add a location type with the given name and associated content types."""
    try:
        location_type = LocationType.objects.get(name=name)
    except LocationType.DoesNotExist:
        content_types = ContentType.objects.get_for_models(*model_types)
        parent = LocationType.objects.get_by_natural_key(*ancestry) if ancestry else None
        location_type = LocationType(
            name=name,
            parent=parent,
        )
        location_type.validated_save()
        location_type.content_types.set(content_types.values())

    return location_type


def add_location(name: str, location_type: LocationType, *ancestry: str, status="Active") -> Location:
    """Add a location with the given name and location type."""
    try:
        location = Location.objects.get(name=name, location_type=location_type)
    except Location.DoesNotExist:
        parent = Location.objects.get_by_natural_key(*ancestry) if ancestry else None
        status = Status.objects.get(name=status)
        location = Location(name=name, location_type=location_type, parent=parent, status=status)
        location.validated_save()
    return location


def add_device_type(manufacturer_name: str, model: str) -> DeviceType:
    """Add a device type with the given manufacturer and model."""
    manufacturer, _ = Manufacturer.objects.get_or_create(name=manufacturer_name)
    device_type, _ = DeviceType.objects.get_or_create(
        model=model,
        manufacturer=manufacturer,
    )
    return device_type


def add_interface_template(name: str, device_type: DeviceType, type="other", **defaults) -> InterfaceTemplate:
    """Add an interface template with the given name to the device type."""
    from nautobot.dcim.models import InterfaceTemplate

    interface_template, _ = InterfaceTemplate.objects.get_or_create(
        device_type=device_type,
        name=name,
        defaults={"type": type, **defaults},
    )
    return interface_template


def add_front_port_template(name: str, rear_port_name: str, device_type: DeviceType):
    """Add a front port template with the given name to the device type."""
    from nautobot.dcim.models import FrontPortTemplate, RearPortTemplate

    rear_port_template, _ = RearPortTemplate.objects.get_or_create(
        device_type=device_type,
        name=rear_port_name,
        type="other",
    )

    front_port_template, _ = FrontPortTemplate.objects.get_or_create(
        device_type=device_type,
        name=name,
        defaults={
            "rear_port_template": rear_port_template,
            "type": "other",
        },
    )
    return front_port_template, rear_port_template


def add_device(name: str, device_type: DeviceType, location: Location, role: Role, status="Active") -> Device:
    """Add a device with the given name, device type, location, and role."""
    try:
        device = Device.objects.get(name=name)
    except Device.DoesNotExist:
        status = Status.objects.get(name=status)
        device = Device(
            name=name,
            device_type=device_type,
            location=location,
            role=role,
            status=status,
        )
        device.validated_save()
    return device
