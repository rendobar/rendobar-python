"""Plumbing every resource shares, sync and async: argument checks, the page type, and response readers.

No I/O here. A resource method builds its request from a generated core call
and reads the answer with one of the readers below (`one`, `listed`, `paged`,
`union`, `empty`), so every method returns the public model it promises.

A reader parses the response body itself rather than trusting the type the
core parsed it into. The core inlines each operation's response, so the same
resource (a storage connection, an asset) comes back as a different generated
class from get, list and update. Reading the body into one public model gives
the caller one type per resource. Unknown fields are kept (`model_extra`), and
an enum value newer than this SDK is a plain string, so a newer API parses.
"""
# pyright: strict
from __future__ import annotations

import re
from typing import Callable, Dict, Generic, Iterator, List, Mapping, Optional, Protocol, Sequence, Tuple, Type, TypeVar

import httpx
import pydantic

from ._errors import InvalidArgumentError, ResponseValidationError, as_list, as_mapping, is_text

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)
Item = TypeVar("Item")
Meta = TypeVar("Meta")
Model = TypeVar("Model", bound=pydantic.BaseModel)


class Response(Protocol[T_co]):
    """What a call through the core returns: the core's HttpResponse, or a `Fetched` result."""

    @property
    def headers(self) -> Mapping[str, str]: ...

    @property
    def data(self) -> T_co: ...


class Envelope(Protocol[T_co]):
    """A response body that wraps its payload in `data`."""

    @property
    def data(self) -> T_co: ...


class Sent(Protocol):
    """A generated core call's answer: its headers and the raw httpx response."""

    @property
    def headers(self) -> Dict[str, str]: ...

    @property
    def response(self) -> httpx.Response: ...


class Fetched(Generic[T]):
    """A result read from a response, with the headers the deprecation check reads."""

    def __init__(self, headers: Mapping[str, str], data: T) -> None:
        self.headers = headers
        self.data = data


class Page(Generic[Item, Meta]):
    """One page of a list: `data` (the items) and `meta` (the totals the list reports, such as `total`).

    Iterate it, or take `len()`, for the items.
    """

    def __init__(self, data: List[Item], meta: Meta) -> None:
        self.data = data
        self.meta = meta

    def __iter__(self) -> Iterator[Item]:
        return iter(self.data)

    def __len__(self) -> int:
        return len(self.data)

    def __repr__(self) -> str:
        return f"Page({len(self.data)} items, meta={self.meta!r})"


# ── arguments, checked before any request ──────────────────────────────

_PATH_SEGMENT = re.compile(r"^[A-Za-z0-9._-]+$")


def path_segment(name: str, value: str) -> str:
    """`value` when it is safe as one URL path segment (an id, a job type), else InvalidArgumentError."""
    if not is_text(value) or not _PATH_SEGMENT.match(value) or value in (".", ".."):
        raise InvalidArgumentError(f"{name} must be letters, digits, '.', '_' or '-', such as job_abc123. Got {value!r}.")
    return value


def _whole(name: str, value: object, minimum: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise InvalidArgumentError(f"{name} must be a whole number of {minimum} or more. Got {value!r}.")


def whole(name: str, value: Optional[int], minimum: int) -> None:
    """InvalidArgumentError for a value that is set and is not a whole number of at least `minimum`."""
    if value is not None:
        _whole(name, value, minimum)


def page_window(limit: Optional[int], offset: Optional[int]) -> None:
    """InvalidArgumentError for a page size below 1, a negative offset, or either not a whole number. The API sets the maximum."""
    whole("limit", limit, 1)
    whole("offset", offset, 0)


def text(name: str, value: Optional[str]) -> None:
    """InvalidArgumentError for a value that is set and is not a string."""
    if value is not None and not is_text(value):
        raise InvalidArgumentError(f"{name} must be a string. Got {type(value).__name__}.")


def texts(name: str, values: Sequence[str]) -> List[str]:
    """`values` as a list when it is a list of strings (not one string), else InvalidArgumentError."""
    items = None if isinstance(values, str) else as_list(values)
    if items is None or not all(isinstance(item, str) for item in items):
        raise InvalidArgumentError(f"{name} must be a list of strings. Got {values!r}.")
    return [str(item) for item in items]


# ── reading responses ──────────────────────────────────────────────────

Reader = Callable[[httpx.Response], T]


def _body(response: httpx.Response) -> object:
    try:
        decoded: object = response.json()
    except ValueError:
        return response.text
    return decoded


def unread(response: httpx.Response, body: object) -> ResponseValidationError:
    return ResponseValidationError(
        f"The API answered {response.status_code} with a body this SDK cannot read. Upgrade rendobar, or read `body`.",
        status_code=response.status_code, body=body, headers=dict(response.headers),
    )


def _envelope(response: httpx.Response) -> Tuple[object, Mapping[str, object]]:
    body = _body(response)
    mapping = as_mapping(body)
    if mapping is None or "data" not in mapping:
        raise unread(response, body)
    return body, mapping


def one(model: Type[Model]) -> Reader[Model]:
    """Reads `{data: {...}}` as `model`."""
    def read(response: httpx.Response) -> Model:
        body, envelope = _envelope(response)
        try:
            return model.model_validate(envelope["data"])
        except pydantic.ValidationError:
            raise unread(response, body) from None
    return read


def union(adapter: "pydantic.TypeAdapter[T]") -> Reader[T]:
    """Reads `{data: ...}` as the union `adapter` validates, such as the two answers of compose.validate."""
    def read(response: httpx.Response) -> T:
        body, envelope = _envelope(response)
        try:
            return adapter.validate_python(envelope["data"])
        except pydantic.ValidationError:
            raise unread(response, body) from None
    return read


def _items(model: Type[Model], response: httpx.Response, body: object, data: object) -> List[Model]:
    items = as_list(data)
    if items is None:
        raise unread(response, body)
    try:
        return [model.model_validate(item) for item in items]
    except pydantic.ValidationError:
        raise unread(response, body) from None


def listed(model: Type[Model]) -> Reader[List[Model]]:
    """Reads `{data: [...]}` as a list of `model`."""
    def read(response: httpx.Response) -> List[Model]:
        body, envelope = _envelope(response)
        return _items(model, response, body, envelope["data"])
    return read


MetaModel = TypeVar("MetaModel", bound=pydantic.BaseModel)


def paged(model: Type[Model], meta: Type[MetaModel]) -> Reader[Page[Model, MetaModel]]:
    """Reads `{data: [...], meta: {...}}` as a Page of `model` with `meta`."""
    def read(response: httpx.Response) -> Page[Model, MetaModel]:
        body, envelope = _envelope(response)
        items = _items(model, response, body, envelope["data"])
        try:
            return Page(items, meta.model_validate(envelope.get("meta")))
        except pydantic.ValidationError:
            raise unread(response, body) from None
    return read


def empty(response: httpx.Response) -> None:
    """A success with nothing to read (204), or a body this method does not return."""
    return None
