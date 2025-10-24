"""Utility methods for the jobs."""

from typing import TypeVar

from django.db.models import Model, Q, QuerySet

ModelType = TypeVar("ModelType", bound=Model)


def filter_kwargs(obj: ModelType, **kwargs: type[Model]) -> dict[str, ModelType | None]:
    """Build a set of kwargs based on matching model type.

    This method will iterate the kwargs key/value pairs and compare if the provided object
    is an instance of the value (which should be a type). If it is, then the return kwargs
    dictionary will be updated with that keyword argument's name and the object as the value.
    If the object is not an instance of the type, then that keyword value is set to None.

    Args:
        obj (Model): The input object to match.
        kwargs (type[Model]): keyword argument types to match.

    Returns:
        ModelType: A dictionary that can be used to populate the `filter_objects` method kwargs.
    """
    return_kwargs = {}
    for arg_name, model_type in kwargs.items():
        if isinstance(obj, model_type):
            return_kwargs[arg_name] = obj
        else:
            return_kwargs[arg_name] = None
    return return_kwargs


def filter_objects(objects: Model | QuerySet[ModelType], **kwargs: Model | QuerySet | None) -> QuerySet[ModelType]:
    """Helper function to build a query from kwargs."""
    if objects is None:
        raise ValueError("Must supply a non-None queryset.")

    filter = Q()
    for field_name, constraint in kwargs.items():
        if constraint:
            filter &= Q(**{field_name: constraint})

    if isinstance(objects, Model):
        filter &= Q(pk=objects.pk)
        objects = objects.__class__.objects  # type: ignore

    return objects.filter(filter)
