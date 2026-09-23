from typing import Annotated

from bson import ObjectId
from pydantic import BeforeValidator, PlainSerializer


PyObjectId = Annotated[
    ObjectId,
    BeforeValidator(lambda value: ObjectId(value) if not isinstance(value, ObjectId) else value),
    PlainSerializer(lambda value: str(value), return_type=str),
]
