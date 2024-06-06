"""Unit tests for the device component update job."""
from os import path
from unittest.mock import Mock

from nautobot.apps.testing import TestCase
from nautobot.dcim.models import (
    Device,
    Interface,
    InterfaceTemplate,
    RearPort,
    RearPortTemplate,
)

from nautobot.extras.models import Status

from ..device_component_update import FieldUpdate, TemplateUpdate

class ComponentUpdateTestCase(TestCase):
    """Base test case with fixtures."""
    fixtures = [path.join(path.dirname(__file__), "fixtures", "device_component_update.json")]

class TestFieldUpdate(ComponentUpdateTestCase):
    """Unit tests for the FieldUpdate dataclass."""

    def test_get_values_with_default(self):
        """Test get_values with only a name and default value."""
        field_update = FieldUpdate(name="name", default_value="Ethernet2")
        interface = Interface(name="Ethernet1")
        old_value, new_value = field_update.get_values(interface, None)
        self.assertEqual("Ethernet1", old_value)
        self.assertEqual("Ethernet2", new_value)

    def test_get_values_with_template(self):
        """Test get_values with a name and template."""
        field_update = FieldUpdate(name="name")
        interface = Interface(name="Ethernet1")
        interface_template = InterfaceTemplate(name="Ethernet2")
        old_value, new_value = field_update.get_values(interface, interface_template)
        self.assertEqual("Ethernet1", old_value)
        self.assertEqual("Ethernet2", new_value)

    def test_query_manager(self):
        """Test get_values with a real (not string) query manager."""
        field_update = FieldUpdate(name="status", key_field="name", default_value="Offline", query_from=Status.objects)
        device = Device.objects.first()
        interface = Interface(device=device, name="Ethernet1", status=Status.objects.get(name="Active"))
        interface_template = InterfaceTemplate.objects.get(name=device.interfaces.first().name)
        old_value, new_value = field_update.get_values(interface, interface_template)
        self.assertEqual(None, old_value)
        self.assertEqual(Status.objects.get(name="Offline"), new_value)

    def test_query_manager_with_default_value(self):
        """Test get_values with a query manager and default value."""
        field_update = FieldUpdate(
            name="rear_port",
            key_field="name",
            query_from="device.rear_ports",
            default_value="Rear Port",
        )
        device = Device.objects.first()
        front_port = device.front_ports.first()
        rear_port = front_port.rear_port
        old_value, new_value = field_update.get_values(front_port, None)
        self.assertIs(old_value, new_value)
        self.assertEqual(rear_port, new_value)

    def test_query_manager_without_default_value(self):
        """Test get_values with a query manager and no default value."""
        field_update = FieldUpdate(
            name="rear_port",
            template_name="rear_port_template",
            key_field="name",
            query_from="device.rear_ports",
        )
        device = Device.objects.first()
        front_port = device.front_ports.first()
        rear_port1 = front_port.rear_port
        rear_port2 = RearPort(type="other", device=device, name="Rear Port 2")
        rear_port2.validated_save()

        rear_port_template = RearPortTemplate(device_type=device.device_type, type="other", name="Rear Port 2")
        rear_port_template.validated_save()
        front_port_template = device.device_type.front_port_templates.first()
        front_port_template.rear_port_template = rear_port_template
        front_port_template.validated_save()
        old_value, new_value = field_update.get_values(front_port, front_port_template)
        self.assertEqual(old_value, rear_port1)
        self.assertEqual(new_value, rear_port2)

    def test_update_with_no_default_or_template(self):
        """Test a field update where only the name is supplied."""
        field_update = FieldUpdate(name="name")
        self.assertRaises(ValueError, field_update.update, None, None)

    def test_update_with_nothing_changed(self):
        """Test a field update where the field has not changed."""
        field_update = FieldUpdate(name="name")
        device = Device.objects.first()
        interface = device.interfaces.first()
        interface_template = InterfaceTemplate.objects.get(name=interface.name)
        job_mock = Mock()
        field_update.update(job_mock, interface, interface_template)
        job_mock.logger.info.assert_not_called()

    def test_update(self):
        """Test a field update where the field has changed."""
        field_update = FieldUpdate(name="name")
        device = Device.objects.first()
        interface = device.interfaces.first()
        interface_template = InterfaceTemplate(device_type=device.device_type, name="Interface 1")
        job_mock = Mock()
        field_update.update(job_mock, interface, interface_template)
        self.assertEqual("Interface 1", interface.name)
        job_mock.logger.info.assert_called()


class TestTemplateUpdate(ComponentUpdateTestCase):
    """Unit tests for the TemplateUpdate dataclass."""
    def test_new_component(self):
        """Confirm that new components are created."""
        template_update = TemplateUpdate(
            src="interface_templates",
            dst="interfaces",
            key_field="name",
            fields=[
                "name",
                "type",
                FieldUpdate(name="status", key_field="name", default_value="Active", query_from=Status.objects),
            ]
        )
        device = Device.objects.first()
        device_type = device.device_type
        template = device_type.interface_templates.first()
        device.interfaces.get(name=template.name).delete()
        self.assertRaises(Interface.DoesNotExist, device.interfaces.get, name=template.name)
        job_mock = Mock()
        template_update.update(job_mock, device_type, device)
        class PrefixStr(str):
            def __eq__(self, other: str):
                return other.startswith(self)

        job_mock.logger.info.assert_called_with(PrefixStr("Created"), "Interface", extra={"object": device})
        self.assertEqual("Interface", device.interfaces.get(name="Interface").name)

    def test_validation_error(self):
        """Confirm that validation errors are logged."""
        template_update = TemplateUpdate(
            src="interface_templates",
            dst="interfaces",
            key_field="name",
            fields=["name"]
        )
        device = Device.objects.first()
        device_type = device.device_type
        template = device_type.interface_templates.first()
        device.interfaces.get(name=template.name).delete()
        self.assertRaises(Interface.DoesNotExist, device.interfaces.get, name=template.name)
        job_mock = Mock()
        template_update.update(job_mock, device_type, device)
        self.assertRaises(Interface.DoesNotExist, device.interfaces.get, name=template.name)
        last_log = job_mock.logger.info.mock_calls[-1]
        print(last_log)
        self.assertTrue(last_log.args[0].startswith("Validation failed"))
        self.assertEqual(last_log.kwargs["extra"]["object"].name, "Interface")
