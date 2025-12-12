import warnings

# Suppress Pydantic deprecation warnings from Vanna library
# This is a known issue in Vanna 2.0 with Pydantic v2
# The warning is about class-based config being deprecated in favor of ConfigDict
# We filter by module path to catch all Pydantic deprecation warnings from Vanna
warnings.filterwarnings(
    'ignore',
    message='.*Support for class-based `config` is deprecated.*',
)
warnings.filterwarnings(
    'ignore',
    module='vanna.core.tool.models',
)

from . import models
