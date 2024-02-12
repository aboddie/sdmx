"""Information related to the SDMX-REST web service standard."""
import abc
import re
from copy import copy
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar, Dict, Optional
from urllib.parse import urlsplit, urlunsplit

if TYPE_CHECKING:
    import sdmx.source

# Mapping from Resource value to class name.
CLASS_NAME = {
    "dataflow": "DataflowDefinition",
    "datastructure": "DataStructureDefinition",
}

# Inverse of :data:`CLASS_NAME`.
VALUE = {v: k for k, v in CLASS_NAME.items()}

#: Response codes defined by the SDMX-REST standard.
RESPONSE_CODE = {
    200: "OK",
    304: "No changes",
    400: "Bad syntax",
    401: "Unauthorized",
    403: "Semantic error",  # or "Forbidden"
    404: "Not found",
    406: "Not acceptable",
    413: "Request entity too large",
    414: "URI too long",
    500: "Internal server error",
    501: "Not implemented",
    503: "Unavailable",
}


class QueryType(str, Enum):
    """High-level types of SDMX REST queries."""

    availability = "availability"
    data = "data"
    metadata = "metadata"
    schema = "schema"
    structure = "structure"

    # SDMX 3.0 only
    registration = "registration"


class Resource(str, Enum):
    """Enumeration of SDMX-REST API resources.

    This class merges the "resources" defined in Section V of the SDMX 2.1 and 3.0
    standards; in the latter, only five values (availability, data, metadata, schema,
    structure) are used as the first part of a URL path; however, the choice of this
    first part and allowable query parameters depend on the more detailed list.

    ============================= ======================================================
    :class:`Enum` member          :mod:`sdmx.model` class
    ============================= ======================================================
    ``actualconstraint``          :class:`.ContentConstraint`
    ``agencyscheme``              :class:`.AgencyScheme`
    ``allowedconstraint``         :class:`.ContentConstraint`
    ``attachementconstraint``     :class:`.AttachmentConstraint`
    ``availableconstraint``       :class:`.ContentConstraint`
    ``categorisation``            :class:`.Categorisation`
    ``categoryscheme``            :class:`.CategoryScheme`
    ``codelist``                  :class:`.Codelist`
    ``conceptscheme``             :class:`.ConceptScheme`
    ``contentconstraint``         :class:`.ContentConstraint`
    ``customtypescheme``          :class:`.CustomTypeScheme`.
    ``data``                      :class:`.DataSet`
    ``dataflow``                  :class:`Dataflow(Definition) <.BaseDataflow>`
    ``dataconsumerscheme``        :class:`.DataConsumerScheme`
    ``dataproviderscheme``        :class:`.DataProviderScheme`
    ``datastructure``             :class:`DataStructureDefinition <.BaseDataStructureDefinition>`
    ``hierarchicalcodelist``      :class:`.v21.HierarchicalCodelist`.
    ``metadata``                  :class:`MetadataSet <.BaseMetadataSet>`.
    ``metadataflow``              :class:`Metadataflow(Definition) <.Metadataflow>`
    ``metadatastructure``         :class:`MetadataStructureDefinition <.BaseMetadataStructureDefinition>`
    ``namepersonalisationscheme`` :class:`.NamePersonalisationScheme`.
    ``organisationscheme``        :class:`.OrganisationScheme`
    ``provisionagreement``        :class:`.ProvisionAgreement`
    ``rulesetscheme``             :class:`.RulesetScheme`.
    ``structure``                 Mixed.
    ``structureset``              :class:`.StructureSet`.
    ``transformationscheme``      :class:`.TransformationScheme`.
    ``userdefinedoperatorscheme`` :class:`.UserdefinedoperatorScheme`.
    ``vtlmappingscheme``          :class:`.VTLMappingScheme`.
    ----------------------------- ------------------------------------------------------
    ``organisationunitscheme``    Not implemented.
    ``process``                   Not implemented.
    ``reportingtaxonomy``         Not implemented.
    ``schema``                    Not implemented.
    ============================= ======================================================

    """  # noqa: E501

    actualconstraint = "actualconstraint"
    agencyscheme = "agencyscheme"
    allowedconstraint = "allowedconstraint"
    attachementconstraint = "attachementconstraint"
    availableconstraint = "availableconstraint"
    categorisation = "categorisation"
    categoryscheme = "categoryscheme"
    codelist = "codelist"
    conceptscheme = "conceptscheme"
    contentconstraint = "contentconstraint"
    customtypescheme = "customtypescheme"
    data = "data"
    dataconsumerscheme = "dataconsumerscheme"
    dataflow = "dataflow"
    dataproviderscheme = "dataproviderscheme"
    datastructure = "datastructure"
    hierarchicalcodelist = "hierarchicalcodelist"
    metadata = "metadata"
    metadataflow = "metadataflow"
    metadatastructure = "metadatastructure"
    namepersonalisationscheme = "namepersonalisationscheme"
    organisationscheme = "organisationscheme"
    organisationunitscheme = "organisationunitscheme"
    process = "process"
    provisionagreement = "provisionagreement"
    reportingtaxonomy = "reportingtaxonomy"
    rulesetscheme = "rulesetscheme"
    schema = "schema"
    structure = "structure"
    structureset = "structureset"
    transformationscheme = "transformationscheme"
    userdefinedoperatorscheme = "userdefinedoperatorscheme"
    vtlmappingscheme = "vtlmappingscheme"

    @classmethod
    def from_obj(cls, obj):
        """Return an enumeration value based on the class of `obj`."""
        value = obj.__class__.__name__
        return cls[VALUE.get(value, value)]

    @classmethod
    def class_name(cls, value: "Resource", default=None) -> str:
        """Return the name of a :mod:`sdmx.model` class from an enum value.

        Values are returned in lower case.
        """
        return CLASS_NAME.get(value.value, value.value)

    @classmethod
    def describe(cls):
        return "{" + " ".join(v.name for v in cls._member_map_.values()) + "}"


@dataclass
class Parameter(abc.ABC):
    """SDMX query parameter."""

    name: str

    #: Allowable values.
    values: set = field(default_factory=set)

    #: Default value.
    default: Optional[str] = None

    @abc.abstractmethod
    def handle(self, parameters: Dict[str, Any], *args) -> Dict[str, str]:
        """Return a dict to update :attr:`.URL.path` or :attr:`.URL.query`."""


@dataclass
class PathParameter(Parameter):
    """SDMX query parameter appearing as a part of the path component of a URL."""

    def handle(self, parameters, *args):
        """Return a length-1 dict to update :attr:`.URL.path`."""
        # Retrieve the value from `parameters`
        value = parameters.pop(self.name, self.default)
        # Check against allowable values
        assert value in self.values or 0 == len(self.values)
        # Return
        return {self.name: value}


@dataclass
class QueryParameter(PathParameter):
    """SDMX query parameter appearing as part of the query string component of a URL."""

    def __post_init__(self):
        # Convert self.name to lowerCamelCase as appearing in query strings
        self.camelName = re.sub(r"_([a-z])", lambda x: x.group(1).upper(), self.name)

    def handle(self, parameters, *args):
        """Return a length-0 or -1 dict to update :attr:`.URL.query`."""
        if present := {self.name, self.camelName} & set(parameters):
            if 2 == len(present):
                raise ValueError(f"Cannot give both {self.name} and {self.camelName}")

            value = parameters.pop(present.pop())
            assert value in self.values or 0 == len(self.values)
            return {self.camelName: value}
        else:
            return {}


@dataclass
class AgencyParam(PathParameter):
    """Handle the ``agencyID`` parameter."""

    def handle(self, parameters, source, *args):
        """Default to the ID of :attr:`.URL.source`."""
        parameters.setdefault(self.name, getattr(source, "id", None))
        return super().handle(parameters)


@dataclass
class PositiveIntParam(QueryParameter):
    """A query parameter that must be a positive integer."""

    def handle(self, parameters, *args):
        result = super().handle(parameters)
        try:
            k = list(result)[0]
        except IndexError:
            return result
        else:
            if result[k] <= 0:
                raise ValueError(f"{k} must be positive integer; got {result[k]}")
            else:
                result[k] = str(k)
                return result


# Todo: transcribe:
# - common:IDType
# - common:NCNameIDType
# - common:VersionType

PARAM: Dict[str, Parameter] = {
    # Path parameters
    "agency_id": AgencyParam("agency_id"),
    "resource_id": PathParameter("resource_id", set(), "all"),
    #
    # Query parameters
    # §4.4 Data queries
    "start_period": QueryParameter("start_period"),  # Also availability
    "end_period": QueryParameter("end_period"),  # Also availability
    "updated_after": QueryParameter("updated_after"),  # Also availability
    "first_n_observations": PositiveIntParam("first_n_observations"),
    "last_n_observations": PositiveIntParam("last_n_observations"),
    "dimension_at_observation": QueryParameter("dimension_at_observation"),
    "include_history": QueryParameter("include_history", {True, False}),
    # §4.5 Schema queries — may be 2.1 only
    "explicit_measure": QueryParameter("explicit_measure", {True, False}),
    # §4.6 Availability queries — may be 2.1 only
    "mode": QueryParameter("mode", {"available", "exact"}),
}


class URL(abc.ABC):
    """Utility class to build URLs for SDMX REST web service queries.

    Parameters
    ----------
    source : .Source
        Provides a base URL (API entry point) and optional modification of the complete
        URL.
    resource_type : .Resource
        Indicates the type of query to be made.
    """

    #: SDMX REST web service to query.
    source: "sdmx.source.Source"

    #: Type of resource to be retrieved; a member of :class:`.Resource`.
    resource_type: Resource

    query_type: QueryType

    #: Pieces for the hierarchical path component of the URL.
    _path: Dict[str, Optional[str]]
    #: Pieces for the query component of the URL.
    _query: Dict[str, str]

    #: Keyword arguments to the constructor
    _params: dict

    _all_parameters: ClassVar[Dict[Any, Parameter]]

    def __init__(self, source: "sdmx.source.Source", resource_type: Resource, **kwargs):
        # Store the keyword arguments
        params = copy(kwargs)
        params_dict = params.pop("params", {})
        if overlap := set(params) & set(params_dict):
            raise ValueError(f"Duplicate values for query parameters {overlap}")
        params.update(params_dict)

        self._params = params
        self.source = source
        self.resource_type = resource_type

        self.identify_query_type()

        self._path = dict()
        self._query = dict()

        # Dispatch to a method appropriate to the query type
        getattr(self, f"handle_{self.query_type.name}")()

        if len(self._params):
            # print(f"{self.path = }\n{self.query = }")
            raise ValueError(f"Unexpected/unhandled parameters {self._params}")

    # General-purpose methods

    def handle_path_params(self, expr: str) -> None:
        """Extend :attr:`.path` with parts from `expr`, a "/"-delimited string."""
        for name in expr.split("/"):
            p = self._all_parameters[name]
            self._path.update(p.handle(self._params, self.source))

    def handle_query_params(self, expr: str) -> None:
        """Extend :attr:`.query` with parts from `expr`, a " "-delimited string.

        - Uses distinct :class:`.Parameter` per :attr:`.query_type`.
        """
        for name in expr.split():
            p = self._all_parameters[(name, self.query_type)]
            self._query.update(p.handle(self._params))

    def handle_data(self) -> None:
        self._path.update({self.resource_type.name: None})

        self._path["flow_ref"] = self._params.pop("resource_id")

        if "key" in self._params:
            self._path["key"] = self._params.pop("key")

        # TODO handle providerRef

    handle_metadata = handle_data

    def handle_schema(self) -> None:
        self._path.update({self.resource_type.name: None})
        self.handle_path_params("context/agency_id/resource_id/version")

    @abc.abstractmethod
    def handle_structure(self) -> None:
        pass

    def identify_query_type(self):
        """Identify a :class:`.QueryType` given arguments."""
        # TODO handle availability
        try:
            # data, metadata, schema
            self.query_type = QueryType[self.resource_type.name]
        except KeyError:
            self.query_type = QueryType["structure"]

    def join(self) -> str:
        """Join the URL parts, returning a complete URL."""

        # Keep the URL scheme, netloc, and any path from the source's base URL
        parts = list(urlsplit(self.source.url)[:3]) + [None, None]
        # Assemble path string
        parts[2] = "/".join(
            [parts[2] or ""] + [(value or name) for name, value in self._path.items()]
        )
        # Assemble query string
        parts[3] = "&".join(f"{k}={v}" for k, v in self._query.items())

        return urlunsplit(parts)
